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
import yaml

from sdk.python.module.module import Module
from sdk.python.module.helpers.message import Message

import sdk.python.utils.exceptions as exception

class Watchdog(Module):
    # What to do when initializing
    def on_init(self):
        # variables
        self.supported_manifest_schema = 2
        # load the manifest file
        self.manifest = None
        manifest_file = "manifest.yml"
        if not os.path.isfile(manifest_file): 
            print "Manifest not found, refusing to start"
            sys.exit(1)
        with open(manifest_file) as f: content = f.read()
        # ensure the manifest is valid
        try:
            manifest = yaml.load(content, Loader=yaml.SafeLoader)
        except Exception,e: 
            print "invalid manifest file in "+manifest_file+" - "+exception.get(e)
            sys.exit(1)
        if manifest["manifest_schema"] != self.supported_manifest_schema:
                print "Unsupported manifest schema v"+str(manifest["manifest_schema"])
                sys.exit(1)
        for setting in ["manifest_schema", "package", "revision", "version", "branch", "github", "dockerhub", "modules"]:
            if setting not in manifest:
                print setting+" is missing from manifest"
                sys.exit(1)
        # embed default config into the manifest
        manifest["default_config"] = self.load_default_config()
        self.manifest = manifest
        # set watchdog service name
        self.scope = "system"
        # TODO: with random multiple manifests will stay around
        self.name = "watchdog_"+self.manifest["package"]
        self.fullname = self.scope+"/"+self.name
        # array of modules
        self.modules = [] 
        # map module fullname with thread
        self.threads = {}
        self.parse_modules(os.getenv("EGEOFFREY_MODULES", None))
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
        # EGEOFFREY_MODULESS format: package1/file1[=alias1],package2/file2[=alias2] etc.
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
            # ensure the module exists
            if not os.path.isfile(entry["package"]+"/"+entry["file"]+".py"):
                print "Module "+entry["package"]+"/"+entry["file"]+" not found, skipping"
                return
            # import the class from the module
            imported_module = __import__(entry["package"]+"."+entry["file"], fromlist=[classname])
            # reload the code
            reload(imported_module)
            # crate the object
            class_object = getattr(imported_module, classname)
            thread = class_object(entry["scope"], entry["name"])
            # set attributes
            hasher = hashlib.md5()
            hasher.update(repr(imported_module))
            thread.version = str(self.manifest["version"])+"-"+str(self.manifest["revision"])+" ("+str(self.manifest["branch"])+")"
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
        self.join()
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
            self.sleep(1)
            
    def load_default_config(self):
        config_dir = "default_config"
        default_config = []
        if not os.path.isdir(config_dir): return default_config
        # walk through the filesystem containing the default configuration
        for (current_path, dirnames, filenames) in os.walk(config_dir): 
            for filename in filenames:
                if filename[0] == ".": continue
                file = current_path+os.sep+filename
                # parse the file paths
                name, extension = os.path.splitext(file)
                if extension != ".yml": continue
                # remove base configuration dir to build the topic
                topic = name.replace(config_dir+os.sep,"")
                # read the file's content
                with open(file) as f: content = f.read()
                # ensure the yaml file is valid
                try:
                    content = yaml.load(content, Loader=yaml.SafeLoader)
                except Exception,e: 
                    self.log_warning("configuration file in an invalid YAML format: "+filename+" - "+exception.get(e))
                    continue
                # update the index with the corresponding hash
                default_config.append({topic: content})
        return default_config
        
    # What to do when running    
    def on_start(self):
        # clear up previous manifest if any
        message = Message(self)
        message.recipient = "*/*"
        message.command = "MANIFEST"
        message.args = self.manifest["package"]
        message.set_null()
        message.retain = True 
        self.send(message)
        # publish the new manifest
        # TODO: use the manifest to check SDK required version
        message = Message(self)
        message.recipient = "*/*"
        message.command = "MANIFEST"
        message.args = self.manifest["package"]
        message.set_data(self.manifest)
        message.retain = True 
        self.send(message)
        # start all the requested modules
        for entry in self.modules:
            self.start_module(entry)
            self.sleep(0.1)
        self.sleep(60)
        # loop forever
        while True:
            self.sleep(10)
        
    # What to do when shutting down
    def on_stop(self):
        # remove the manifest
        message = Message(self)
        message.recipient = "*/*"
        message.command = "MANIFEST"
        message.args = self.manifest["package"]
        message.set_null()
        message.retain = True 
        self.send(message)

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
