import threading
import os
import time
from abc import ABCMeta, abstractmethod
from datetime import datetime

from sdk.message import Message
from sdk.mqtt_client import Mqtt_client
from sdk.cache import Cache
from sdk.session import Session
import sdk.utils.exceptions as exception
import sdk.utils.constants as constants

# Module class from which all the components inherits common functionalities
class Module(threading.Thread):
    # used for enforcing abstract methods
    __metaclass__ = ABCMeta 
    
    # initialize the class and set the variables
    def __init__(self, scope, name):
        # thread init
        super(Module, self).__init__()
        # set name of this module
        self.scope = scope
        self.name = name
        self.fullname = scope+"/"+name
        self.watchdog = None
        # module version
        self.version = constants.VERSION
        self.build = ""
        # gateway settings
        self.gateway_hostname = os.getenv("MYHOUSE_GATEWAY_HOSTNAME", "localhost")
        self.gateway_port = int(os.getenv("MYHOUSE_GATEWAY_PORT", 443))
        self.gateway_transport = os.getenv("MYHOUSE_GATEWAY_TRANSPORT", "websockets")
        self.gateway_ssl = bool(int(os.getenv("MYHOUSE_GATEWAY_SSL", False)))
        self.gateway_ca_cert = os.getenv("MYHOUSE_GATEWAY_CA_CERT", None)
        self.gateway_certfile = os.getenv("MYHOUSE_GATEWAY_CERTFILE", None)
        self.gateway_keyfile = os.getenv("MYHOUSE_GATEWAY_KEYFILE", None)
        # house settings
        self.house_id = os.getenv("MYHOUSE_ID", "default_house")
        self.house_passcode = os.getenv("MYHOUSE_PASSCODE", "")
        # debug
        self.debug = bool(int(os.getenv("MYHOUSE_DEBUG", False)))
        self.verbose = False
        # logging
        self.logging_remote = bool(int(os.getenv("MYHOUSE_LOGGING_REMOTE", True)))
        self.logging_local = bool(int(os.getenv("MYHOUSE_LOGGING_LOCAL", True)))
        # status
        self.connected = False
        self.configured = True # by default no configuration is required to start
        self.stopping = False
        # initialize mqtt client for connecting to the bus
        self.__mqtt = Mqtt_client(self)
        # initialize internal cache
        self.cache = Cache() 
        # initialize session manager
        self.sessions = Session(self)
        # call module implementation of init
        try:
            self.log_debug("Initializing module...")
            self.on_init()
        except Exception,e: 
            self.log_error("runtime error during on_init(): "+exception.get(e))

    # Add a listener for the given configuration request (will call on_configuration())
    def add_configuration_listener(self, args, wait_for_it=False):
        return self.__mqtt.add_listener("controller/config", "*/*", "CONF", args, wait_for_it)

    # add a listener for the messages addressed to this module (will call on_message())
    def add_request_listener(self, from_module, command, args):
        return self.__mqtt.add_listener(from_module, self.fullname, command, args, False)
    
    # add a listener for broadcasted messages from the given module (will call on_message())
    def add_broadcast_listener(self, from_module, command, args):
        return self.__mqtt.add_listener(from_module, "*/*", command, args, False)

    # add a listener for intercepting messages from a given module to a given module (will call on_message())
    def add_inspection_listener(self, from_module, to_module, command, args):
        return self.__mqtt.add_listener(from_module, to_module, command, args, False)
    
    # remove a topic previously subscribed
    def remove_listener(self, topic):
        self.__mqtt.unsubscribe(topic)
        
    # send a message to another module
    def send(self, message):
        if self.verbose: self.log_debug("Publishing message "+message.dump())
        # ensure message is valid
        if message.sender == "" or message.recipient == "": 
            self.log_warning("invalid message to send")
            return
        # publish it to the message bus
        if message.is_null: payload = None 
        else: payload = message.get_payload()
        self.__mqtt.publish(message.recipient, message.command, message.args, payload, message.retain)
        
    # log a message
    def __log(self, level, text):
        if self.logging_local:
            print "["+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"]["+self.house_id+"]["+str(self.fullname)+"] "+str(level.upper()) + ": "+str(text)
        if self.logging_remote:
            # send the message to the logger module
            message = Message(self)
            message.recipient = "controller/logger"
            message.command = "LOG"
            message.args = level
            message.set_data(text)
            self.send(message)

    # handle debug logs
    def log_debug(self, text):
        if not self.debug: return
        self.__log("debug", text)
    
    # handle info logs
    def log_info(self, text):
        self.__log("info", text)
    
    # handle warning logs
    def log_warning(self, text):
        self.__log("warning", text)
    
    # handle error logs
    def log_error(self, text):
        self.__log("error", text)
        
    # ensure all the items of an array of settings are included in the configuration object provided
    def is_valid_configuration(self, settings, configuration):
        if not isinstance(configuration, dict): return False
        for item in settings:
            if not item in configuration or configuration[item] is None: 
                self.log_warning("Invalid configuration received, "+item+" missing in "+str(configuration))
                return False
        return True
        
    # run the module, called when starting the thread
    def run(self):
        self.log_info("Starting module v"+self.version+" (build "+self.build+")")
        # connect to the mqtt broker
        self.__mqtt.start()
        # subscribe to any request addressed to this module  
        self.add_request_listener("+/+", "+", "#")
        # subscribe to any configuration aimed for this module  
        self.add_configuration_listener(self.fullname)
        # tell everybody this module has started
        message = Message(self)
        message.recipient = "*/*"
        message.command = "STATUS"
        message.args = "1"
        self.send(message)
        # if the service is not configured (waiting for a configuration file), sleep until it will be
        while not self.configured: 
            time.sleep(1)
        # run the user's callback if configured, otherwise will be started once all the required configuration will be received
        try: 
            self.on_start()
        except Exception,e: 
            self.log_error("runtime error during on_start(): "+exception.get(e))

    # shut down the module, called when stopping the thread
    def join(self):
        self.log_info("Stopping module...")
        self.stopping = True
        # tell everybody this module has stopped
        message = Message(self)
        message.recipient = "*/*"
        message.command = "STATUS"
        message.args = "0"
        self.send(message)
        self.on_stop()
        self.__mqtt.stop()
        
    # What to do when initializing (subclass has to implement)
    @abstractmethod
    def on_init(self):
        pass
        
    # What to do just after connecting (subclass may implement)
    def on_connect(self):
        pass
        
    # What to do when running (subclass has to implement)
    @abstractmethod
    def on_start(self):
        pass
        
    # What to do when shutting down (subclass has to implement)
    @abstractmethod
    def on_stop(self):
        pass
        
    # What to do just after disconnecting (subclass may implement)
    def on_disconnect(self):
        pass

    # What to do when receiving a request for this module (subclass has to implement)
    @abstractmethod
    def on_message(self, message):
        pass

     # What to do when receiving a new/updated configuration for this module (subclass has to implement)
    @abstractmethod
    def on_configuration(self, message):
        pass

