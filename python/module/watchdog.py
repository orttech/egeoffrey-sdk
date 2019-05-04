### Class responsible to start/stop services and monitor their execution
## DEPENDENCIES:
# OS: 
# Python: 

import time
import random
import os
import signal
import sys
import hashlib

from sdk.module.module import Module
from sdk.module.helpers.message import Message

import sdk.utils.exceptions as exception

class Watchdog(Module):
    def __init__(self):
        # call superclass function
        super(Watchdog, self).__init__("system","watchdog_"+str(random.randint(1000,9999)))
        
    # What to do when initializing
    def on_init(self):
        # array of modules
        self.modules = [] 
        # map module fullname with thread
        self.threads = {}
        self.parse_modules(os.getenv("MYHOUSE_MODULES", None))
        # register a handler for SIGINT so to stop all the running threads cleanly
        signal.signal(signal.SIGINT, self.interrupt_handler)
        # subscribe for module discovery requests
        self.add_broadcast_listener("+/+","DISCOVER","#")
    
    # return the module entry associated to the fullname provided
    def get_module(self, fullname):
        name = fullname.split("/")
        if len(name) != 2: return None
        for module in self.modules:
            if module["scope"] == name[0] and module["name"] == name[1]: return module
        return None
    
    # parse the input string and populate the modules data structure accordingly
    def parse_modules(self, input):
        if input is None: return
        input = input.replace(" ","")
        input = input.replace("\t","")
        list = input.split(",")
        print "MYHOUSE_MODULES: "+str(list)
        # MYHOUSE_MODULESS format: package1/file1[=alias1],package2/file2[=alias2] etc.
        for entry in list: 
            # keep track of the alias if provided (package/file=alias)
            if "=" in entry: 
                package_file, alias = entry.split("=")
            else:
                package_file = entry
                alias = None
            if "/" not in package_file: 
                print "Skipping invalid module "+package_file
                continue
            # split the package from the filename (will become scope and module name - unless an alias was provided)
            package, file = package_file.split("/") 
            module = {
                "package": package,
                "file": file,
                "scope": package,
                "started": False,
                "name": alias if alias is not None else file,
                "ping": 0
            }
            module["fullname"] = module["scope"]+"/"+module["name"]
            self.modules.append(module)
            # TODO: periodically check if configured and if not raise a warning
    
    # start an entry of the modules data structure
    def start_module(self, entry):
        # the name of the class is the name of the module with the first capital letter
        if entry["started"]: return
        classname = entry["file"].capitalize() 
        try: 
            # import the class from the module
            # TODO: check if the file exists
            imported_module = __import__(entry["package"]+"."+entry["file"], fromlist=[classname]) 
            reload(imported_module)
            class_object = getattr(imported_module, classname)
            thread = class_object(entry["scope"], entry["name"])
            # set attributes
            hasher = hashlib.md5()
            hasher.update(repr(imported_module))
            thread.build = hasher.hexdigest()[:7]
            thread.daemon = True 
            thread.watchdog = self 
            # run the thread
            thread.start()
            # keep track of the managed thread
            self.threads[entry["fullname"]] = thread 
            entry["started"] = True
        except Exception,e:
            # TODO: print?
            print "Error while running module "+entry["fullname"]+": "+exception.get(e)
    
    # stop an entry of the modules data structure    
    def stop_module(self, entry):
        if not entry["started"]: return
        try:
            self.threads[entry["fullname"]].join()        
        except Exception,e:
            print "Error while stopping module "+entry["fullname"]+": "+exception.get(e)
        entry["started"] = False
        
    # restart a module
    def restart_module(self, module_name):
        module = self.get_module(module_name)
        if module is None: return
        self.log_info("asked to restart module "+module["fullname"])
        self.stop_module(module)
        self.start_module(module)

    # handle SIGINT
    def interrupt_handler(self, sig, frame):
        print("Exiting...")
        for entry in reversed(self.modules):
            # ask all the modules to stop
            self.stop_module(entry)
            #time.sleep(0.1)
        sys.exit(0)
    
    # ping all the modules belonging to this watchdog
    def ping(self):
        for module in self.modules:
            # raise a warning if a module becomes unreachable
            if module["ping"] > 10:
                self.log_warning("module "+module["fullname"]+" is unreachable")
            # periodically ping all registered modules
            message = Message(self)
            message.recipient = module["fullname"]
            message.command = "PING"
            self.log_debug("Pinging "+module["fullname"]+"...")
            module["ping"] = time.time() # keep track of the timestamp of the request
            self.send(message)
            time.sleep(1)
        
    # What to do when running    
    def on_start(self):
        # start all the requested modules
        for entry in self.modules:
            self.start_module(entry)
            time.sleep(0.1)
        time.sleep(60)
        # loop forever, pinging the managed modules from time to time
        while True:
            self.ping()
            time.sleep(5*60)
        
    # What to do when shutting down
    def on_stop(self):
        pass

    # What to do when receiving a request for this module    
    def on_message(self, message):
        # TODO: authentication?
        # handle pong responses
        if message.command == "PONG":
            # get back the module's object
            module = self.get_module(message.sender)
            if module is None: return
            # calculate roundtrip time
            module["ping"] = round(time.time() - module["ping"], 3)
            self.log_debug("Received ping reply from "+module["fullname"]+": "+str(module["ping"])+"ms")
            return
        # reply with the list of managed modules and their status
        elif message.command == "DISCOVER" and message.args == "req":
            self.log_debug("requested module discovery from "+message.sender)
            message = Message(self)
            message.recipient = "*/*"
            message.command = "DISCOVER"
            message.args = "res"
            for module in self.modules:
                module["debug"] = self.threads[module["fullname"]].debug
                module["version"] = self.threads[module["fullname"]].version
                module["build"] = self.threads[module["fullname"]].build
                module["configured"] = self.threads[module["fullname"]].configured
            message.set_data(self.modules)
            self.send(message)
            return
        # set debug at runtime
        elif message.command == "DEBUG":
            module = self.get_module(message.args)
            if module is None: return
            self.log_info("setting debug to "+str(message.get_data())+" to module "+module["fullname"])
            self.threads[message.args].debug = bool(int(message.get_data()))
            module["debug"] = bool(int(self.threads[message.args].debug))
        # stop a started module
        elif message.command == "STOP": 
            module = self.get_module(message.args)
            if module is None: return
            self.log_info("asked to stop module "+module["fullname"])
            self.stop_module(module)
        # start a stopped module
        elif message.command == "START": 
            module = self.get_module(message.args)
            if module is None: return
            self.log_info("asked to start module "+module["fullname"])
            self.start_module(module)
        # restart a stopped module
        elif message.command == "RESTART": 
            module = self.get_module(message.args)
            if module is None: return
            self.log_info("asked to restart module "+module["fullname"])
            self.stop_module(module)
            self.start_module(module)
               
     # What to do when receiving a new/updated configuration for this module    
    def on_configuration(self, message):
        pass
