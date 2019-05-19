### Representation of a message to be sent to the bus
## DEPENDENCIES:
# OS:
# Python: 

import json
import random
import copy

import sdk.constants as constants
import sdk.utils.exceptions as exception

class Message():
    def __init__(self, module=None):
        self.reset()
        # if module is given, set module name as sender and associated house_id
        if module is not None:
            self.sender = module.fullname
            self.house_id = module.house_id
            
    # generate and set a request_id
    def __add_request_id(self):
        self.__payload["request_id"] = random.randint(1,100000)
    
    # clone an object
    def __clone(self, object):
        return copy.deepcopy(object)
            
    # reset the message
    def reset(self):
        # topic from which the message comes from, populated only for incoming messages
        self.topic = ""
        # house id
        self.house_id = ""
        # sender module
        self.sender = ""
        # recipient module
        self.recipient = ""
        # requested command to execute
        self.command = ""
        # arguments of the command
        self.args = ""
        # setup the payload (not directly accessible by the user)
        self.__payload = {}
        self.clear()
        # set to true when payload is null
        self.is_null = False
        # retain the message in the mqtt bus
        self.retain = False
        
    # clear the payload only
    def clear(self):
        # content of the message made up of a unique request_id and user's data
        self.__payload = {
            "request_id": 0,
            "data": {}
        }
        self.__add_request_id()

    # parse a MQTT message (topic and payload)
    def parse(self, topic, payload, retain):
        # split the topic
        topics = topic.split("/")
        # sanity check
        if len(topics) < 8: 
            raise Exception("missing required information in topic")
        if topics[0] != "myHouse" or topics[1] != constants.API_VERSION: 
            raise Exception("invalid api call")
        # store original topic (mainly used by mqtt_client to dispatch the message)
        self.topic = topic
        # store individual topic sections into internal variables
        self.house_id = topics[2]
        self.sender = topics[3]+"/"+topics[4]
        self.recipient = topics[5]+"/"+topics[6]
        self.command = topics[7]
        self.args = "/".join(topics[8:])
        self.retain = retain
        # null payload (for clearing retain flag)
        if payload is None or payload == "":
            self.is_null = True
        else:
            # expecting a json payload
            try: 
                self.__payload = json.loads(payload)
            except Exception,e:
                raise Exception("payload in an invalid JSON format: "+exception.get(e)+" - "+str(payload))

    # set the payload to value
    def set_data(self, value):
        self.__payload["data"] = value
                
    # set key of the payload to value
    def set(self, key, value):
        if not isinstance(self.__payload["data"], dict): self.__payload["data"] = {}
        self.__payload["data"][key] = value
        
    # set the payload to null
    def set_null(self):
        self.is_null = True
        self.__payload = None

    # get the value of key of the payload
    def get(self, key):
        if self.is_null: return None
        if not isinstance(self.__payload["data"], dict): return None
        if "data" not in self.__payload: return None
        if key not in self.__payload["data"]: return None
        return self.__clone(self.__payload["data"][key])
    
    # return true if payload has the given key
    def has(self, key):
        if self.get(key) is None: return False
        return True
        
    # get the value of the payload
    def get_data(self):
        if "data" not in self.__payload: return None
        return self.__clone(self.__payload["data"])
        
    # get the request_id
    def get_request_id(self):
        if "request_id" not in self.__payload: return None
        return self.__payload["request_id"]
        
    # get the payload (not supposed to be called by users
    def get_payload(self):
        return self.__payload
        
    # reply to this message
    def reply(self):
        # swap sender and recipient
        tmp = self.sender 
        self.sender = self.recipient
        self.recipient = tmp
        # clear the content (while keeping original command and args)
        self.topic = "" 
        self.__payload["data"] = {}
    
    # forward this message to another module
    def forward(self, recipient):
        # new sender is the current recipient
        self.sender = self.recipient
        # set the recipient to the provided one
        self.recipient = recipient
        self.topic = ""
        
    # dump the content of this message
    def dump(self):
        if self.is_null: content = "null"
        else: content = str(self.__payload["data"])+" ["+str(self.__payload["request_id"])+"]"
        return "Message("+self.sender+" -> "+self.recipient+": "+self.command+" "+self.args+": "+content+")"