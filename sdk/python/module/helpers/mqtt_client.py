import os
import Queue
import time
import json
import paho.mqtt.client as mqtt
import ssl

import sdk.python.constants as constants
import sdk.python.utils.exceptions as exception
from sdk.python.module.helpers.message import Message

class Mqtt_client():
    def __init__(self, module):
        # we need the module's object to call its methods
        self.__module = module
        # mqtt object
        self.__gateway = None
        # track the topics subscribed
        self.__topics_to_subscribe = []
        self.__topics_subscribed = []
        self.__topics_to_wait = []
        # queue messages while offline
        self.__queue = Queue.Queue(50)
        
    # connect to the MQTT broker
    def __connect(self):
        # setup TLS if needed
        if self.__module.gateway_ca_cert is not None: 
            self.__gateway.tls_set(ca_certs=self.__module.gateway_ca_cert, certfile=self.__module.gateway_certfile, keyfile=self.__module.gateway_keyfile)
            # do not check for certificate validity
            self.__gateway.tls_insecure_set(True)
        # setup SSL if needed
        elif self.__module.gateway_ssl:
            self.__gateway.tls_set(cert_reqs=ssl.CERT_NONE)
        # try to connect to the gateway until succeeding
        while self.__module.connected == False:
            try:
                self.__module.log_debug("Connecting to "+self.__module.gateway_hostname+":"+str(self.__module.gateway_port)+" ("+self.__module.gateway_transport+", ssl="+str(self.__module.gateway_ssl)+")")
                self.__gateway.connect(self.__module.gateway_hostname, self.__module.gateway_port)
                # TODO: this has to be moved into on_connect but is never called if moved
                self.__module.connected = True
                # TODO: last will? e.g. log a disconnecting message
            except Exception,e:
                self.__module.log_error("Unable to connect to "+self.__module.gateway_hostname+":"+str(self.__module.gateway_port)+" - "+exception.get(e))
                self.__module.sleep(10)

    # subscribe to a given topic
    def __subscribe(self, topic, qos=0):
        self.__module.log_debug("Subscribing topic "+topic)
        self.__gateway.subscribe(topic, qos=qos)
        
    # Build the full topic (e.g. myhouse/v1/<house_id>/<from_module>/<to_module>/<command>/<args>)
    def __build_topic(self, from_module, to_module, command, args):
        if args == "": args = "null"
        return "/".join(["myHouse", constants.API_VERSION, self.__module.house_id, from_module, to_module, command, args])

    # publish a given topic 
    def publish(self, to_module, command, args, payload_data, retain=False):
        # serialize the payload in a json format
        payload = payload_data
        if payload is not None: payload = json.dumps(payload)
        # build the topic to publish to
        topic = self.__build_topic(self.__module.fullname, to_module, command, args)
        # publish if connected
        if self.__module.connected:
            info = self.__gateway.publish(topic, payload, retain=retain)
        # queue the message if offline
        else:
            self.__queue.put([topic, payload, retain])
            
    # unsubscribe from a topic
    def unsubscribe(self, topic):
        self.__module.log_debug("Unsubscribing from "+topic)
        self.__topics_subscribed.remove(topic)
        self.__gateway.unsubscribe(topic)
    
    # called from module. Connect to the MQTT broker and subscribe to the requested topics
    def start(self):
        # set client id. Format: myhouse-<house_id>-<scope>-<name>
        self.__client_id = "-".join(["myhouse", self.__module.house_id, self.__module.scope, self.__module.name])
        # get an instance of the MQTT client object
        self.__gateway = mqtt.Client(client_id=self.__client_id, clean_session=True, userdata=None, transport=self.__module.gateway_transport)
        # define what to do upon connect
        def __on_connect(client, userdata, flags, rc):
            try:
                if rc == 0:
                    self.__module.log_debug("Connected to "+self.__module.gateway_hostname+":"+str(self.__module.gateway_port))
                    # call user's callback
                    self.__module.on_connect()
                    # subscribe to the requested topics
                    for topic in self.__topics_to_subscribe: 
                        self.__subscribe(topic)
                        self.__topics_subscribed.append(topic)
                    # if there are message in the queue, send them
                    if self.__queue.qsize() > 0: 
                        while not self.__queue.empty():
                            entry = self.__queue.get()
                            self.__gateway.publish(entry[0], entry[1], retain=entry[2])
                else:
                    # unable to connect, retry
                    self.__module.log_error("Cannot connect: " + connack_string(rc))
                    self.__module.connected = False
                    self.__connect()
            except Exception,e:
                self.__module.log_error("runtime error in __on_connect(): "+exception.get(e))
            
        # what to do when receiving a message
        def __on_message(client, userdata, msg):
            # TODO: what if not intended for this house
            try:
                # parse the incoming request into a message data structure
                message = Message()
                message.parse(msg.topic, msg.payload, msg.retain)
                if self.__module.verbose: self.__module.log_debug("Received message "+message.dump(), False)
            except Exception,e:
                self.__module.log_error("Invalid message received on "+msg.topic+" - "+msg.payload+": "+exception.get(e))
                return
            # dispacth the message
            try:
                # identify the subscribed topic which caused this message to get here
                for pattern in self.__topics_subscribed:
                    if mqtt.topic_matches_sub(pattern, message.topic):
                        # if the message is a configuration
                        if message.sender == "controller/config" and message.command == "CONF":
                            # notify the module about the configuration just received
                            try:
                                # TODO: this is all executed by mqtt network thread so it is blocking. Move it
                                is_valid_configuration = self.__module.on_configuration(message)
                            except Exception,e: 
                                self.__module.log_error("runtime error during on_configuration() - "+message.dump()+": "+exception.get(e))
                                return
                            # if the configuration has not been accepted by the module, ignore it
                            if is_valid_configuration is not None and not is_valid_configuration: return
                            # check if we had to wait for this message to start the module
                            if len(self.__topics_to_wait) > 0:
                                for req_pattern in self.__topics_to_wait:
                                    if mqtt.topic_matches_sub(req_pattern, message.topic):
                                        self.__topics_to_wait.remove(message.topic)
                                        # if there are no more topics to wait for, this service is now configured
                                        if len(self.__topics_to_wait) == 0: 
                                            self.__module.log_info("Configuration completed")
                                            # set the configured flag to true, this will cause the service to start
                                            self.__module.configured = True
                                        else:
                                            self.__module.log_debug("still waiting for configuration on "+str(self.__topics_to_wait))
                        # handle internal messages
                        elif message.command == "PING":
                            message.reply()
                            message.command = "PONG"
                            self.__module.send(message)
                        # notify the module about this message (only if fully configured)
                        else:
                            if self.__module.configured: 
                                try: 
                                    self.__module.on_message(message)
                                except Exception,e: 
                                    self.__module.log_error("runtime error during on_message(): "+exception.get(e))
                        # avoid delivering the same message multiple times for overlapping subscribers
                        return 
            except Exception,e:
                self.__module.log_error("Cannot handle request: "+exception.get(e))

        # what to do upon disconnect
        def __on_disconnect(client, userdata, rc):
            self.__module.connected = False
            # call user's callback
            try: 
                self.__module.on_disconnect()
            except Exception,e: 
                self.__module.log_error("runtime error during on_disconnect(): "+exception.get(e))
            if rc == 0:
                self.__module.log_debug("Disconnected from "+self.__module.gateway_hostname+":"+str(self.__module.gateway_port))
            else:
                self.__module.log_warning("Unexpected disconnection, reconnecting...")
                self.__connect()
            
        # set callbacks for mqtt
        self.__gateway.on_connect = __on_connect
        self.__gateway.on_message = __on_message
        self.__gateway.on_disconnect = __on_disconnect
        # connect to the gateway
        self.__gateway.username_pw_set(self.__module.house_id, password=self.__module.house_passcode)
        self.__connect()
        # start loop (in the background, as an independent thread)
        try: 
            self.__gateway.loop_start()
        except Exception,e: 
            self.__module.log_error("Unexpected runtime error: "+exception.get(e))

    # add a listener for the given request
    def add_listener(self, from_module, to_module, command, args, wait_for_it):
        topic = self.__build_topic(from_module, to_module, command, args)
        if wait_for_it:
            # if this is mandatory topic, unconfigure the module and add it to the list of topics to wait for
            self.__topics_to_wait.append(topic)
            self.__module.configured = False
            self.__module.log_debug("will wait for configuration on "+str(self.__topics_to_wait))
        # if connected, subscribe the topic and keep track of it
        if self.__module.connected: 
            if topic in self.__topics_subscribed: return None
            self.__subscribe(topic)
            self.__topics_subscribed.append(topic)
        # if not connected, will subscribe once connected
        else:
            if topic in self.__topics_to_subscribe: return None
            self.__topics_to_subscribe.append(topic)
        # return the topic so the user can unsubscribe from it if needed
        return topic
            
    # disconnect from the MQTT broker
    def stop(self):
        if self.__gateway == None: return
        self.__gateway.loop_stop()
        self.__gateway.disconnect()
        try:
            self.__module.on_disconnect()
        except Exception,e: 
            self.__module.log_error("runtime error during on_disconnect(): "+exception.get(e))

