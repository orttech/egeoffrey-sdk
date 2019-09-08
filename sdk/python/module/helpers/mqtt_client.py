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
        self.__publish_queue = Queue.Queue(50)
        # queue configuration messages while not configured
        self.__configuration_queue = Queue.Queue(30)
        
    # connect to the MQTT broker
    def __connect(self):
        # setup TLS for tcp transport if needed
        if self.__module.gateway_ssl and self.__module.gateway_transport == "tcp": 
            self.__gateway.tls_set(ca_certs=self.__module.gateway_ca_cert, certfile=self.__module.gateway_certfile, keyfile=self.__module.gateway_keyfile)
            # do not check for certificate validity
            self.__gateway.tls_insecure_set(True)
        # setup SSL for websocket transport if needed
        elif self.__module.gateway_ssl and self.__module.gateway_transport == "websockets":
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
                self.__module.log_warning("Unable to connect to "+self.__module.gateway_hostname+":"+str(self.__module.gateway_port)+" - "+exception.get(e))
                self.__module.sleep(10)

    # subscribe to a given topic
    def __subscribe(self, topic):
        self.__module.log_debug("Subscribing topic "+topic)
        self.__gateway.unsubscribe(topic)
        self.__gateway.subscribe(topic, qos=2)
        
    # Build the full topic (e.g. egeoffrey/v1/<house_id>/<from_module>/<to_module>/<command>/<args>)
    def __build_topic(self, house_id, from_module, to_module, command, args):
        if args == "": args = "null"
        return "/".join(["egeoffrey", constants.API_VERSION, house_id, from_module, to_module, command, args])

    # publish a given topic 
    def publish(self, house_id, to_module, command, args, payload_data, retain=False):
        # serialize the payload in a json format
        payload = payload_data
        if payload is not None: payload = json.dumps(payload)
        # build the topic to publish to
        topic = self.__build_topic(house_id, self.__module.fullname, to_module, command, args)
        # publish if connected
        if self.__module.connected:
            info = self.__gateway.publish(topic, payload, retain=retain, qos=2)
        # queue the message if offline
        else:
            self.__publish_queue.put([topic, payload, retain])
            
    # unsubscribe from a topic
    def unsubscribe(self, topic):
        self.__module.log_debug("Unsubscribing from "+topic)
        self.__topics_subscribed.remove(topic)
        self.__gateway.unsubscribe(topic)
    
    # called from module. Connect to the MQTT broker and subscribe to the requested topics
    def start(self):
        # set client id. Format: egeoffrey-<house_id>-<scope>-<name>
        self.__client_id = "-".join(["egeoffrey", self.__module.house_id, self.__module.scope, self.__module.name])
        # get an instance of the MQTT client object
        if self.__module.persistent_client: self.__module.log_debug("Configuring as persistent mqtt client")
        clean_session = False if self.__module.persistent_client else True
        self.__gateway = mqtt.Client(client_id=self.__client_id, clean_session=clean_session, userdata=None, transport=self.__module.gateway_transport)
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
                    if self.__publish_queue.qsize() > 0: 
                        while not self.__publish_queue.empty():
                            entry = self.__publish_queue.get()
                            self.__gateway.publish(entry[0], entry[1], retain=entry[2], qos=2)
                else:
                    # unable to connect, retry
                    self.__module.log_error("Cannot connect: " + mqtt.connack_string(rc))
                    self.__module.connected = False
                    self.__connect()
            except Exception,e:
                self.__module.log_error("runtime error in __on_connect(): "+exception.get(e))
            
        # what to do when receiving a message
        def __on_message(client, userdata, msg):
            try:
                # parse the incoming request into a message data structure
                message = Message()
                message.parse(msg.topic, msg.payload, msg.retain)
                if self.__module.verbose: self.__module.log_debug("Received message "+message.dump(), False)
            except Exception,e:
                self.__module.log_error("Invalid message received on "+msg.topic+" - "+msg.payload+": "+exception.get(e))
                return
            # ensure this message is for this house
            if message.house_id != "*" and message.house_id != self.__module.house_id:
                self.__module.log_warning("received message for the wrong house "+message.house_id+": "+message.dump())
                return
            # dispatch the message
            try:
                # identify the subscribed topic which caused this message to get here
                for pattern in self.__topics_subscribed:
                    if mqtt.topic_matches_sub(pattern, message.topic):
                        # if the message is a configuration
                        if message.sender == "controller/config" and message.command == "CONF":
                            # TODO: this is all executed by mqtt network thread so it is blocking. Move it
                            # notify the module about the configuration just received
                            try:
                                is_valid_configuration = self.__module.on_configuration(message)
                            except Exception,e: 
                                self.__module.log_error("runtime error during on_configuration() - "+message.dump()+": "+exception.get(e))
                                return
                            # if the configuration has not been accepted by the module (returned False), ignore it
                            if is_valid_configuration is not None and not is_valid_configuration: return
                            # check if we had to wait for this message to start the module
                            configuration_consumed = False
                            if len(self.__topics_to_wait) > 0:
                                for req_pattern in self.__topics_to_wait:
                                    if mqtt.topic_matches_sub(req_pattern, message.topic):
                                        self.__module.log_debug("received configuration "+message.topic)
                                        configuration_consumed = True
                                        self.__topics_to_wait.remove(req_pattern)
                                        # if there are no more topics to wait for, this service is now configured
                                        if len(self.__topics_to_wait) == 0: 
                                            self.__module.log_info("Configuration completed")
                                            # set the configured flag to true, this will cause the service to start (on_start() is in the main thread)
                                            self.__module.configured = True
                                            # now that is configured, if there are configuration messages waiting in the queue, deliver them
                                            if self.__configuration_queue.qsize() > 0: 
                                                while not self.__configuration_queue.empty():
                                                    queued_message = self.__configuration_queue.get()
                                                    try:
                                                        self.__module.on_configuration(queued_message)
                                                    except Exception,e: 
                                                        self.__module.log_error("runtime error during on_configuration() - "+queued_message.dump()+": "+exception.get(e))
                                        else:
                                            self.__module.log_debug("still waiting for configuration on "+str(self.__topics_to_wait))
                            # if this message was not consumed and the module is still unconfigured, queue it, will be delivered once configured
                            if not configuration_consumed and not self.__module.configured:
                                self.__configuration_queue.put(message)
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
        topic = self.__build_topic("+", from_module, to_module, command, args)
        if wait_for_it:
            # if this is mandatory topic, unconfigure the module and add it to the list of topics to wait for
            self.__topics_to_wait.append(topic)
            self.__module.configured = False
            self.__module.log_debug("will wait for configuration on "+topic)
        # if connected, subscribe the topic and keep track of it
        if self.__module.connected: 
            if topic in self.__topics_subscribed: return topic
            self.__subscribe(topic)
            self.__topics_subscribed.append(topic)
        # if not connected, will subscribe once connected
        else:
            if topic in self.__topics_to_subscribe: return topic
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

