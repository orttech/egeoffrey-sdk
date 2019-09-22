import os
import collections
import time
import json
import paho.mqtt.client as mqtt
import ssl
import Queue

import sdk.python.constants as constants
import sdk.python.utils.exceptions as exception
from sdk.python.module.helpers.message import Message
from sdk.python.module.helpers.mqtt_consumer import Mqtt_consumer

class Mqtt_client():
    def __init__(self, module):
        # we need the module's object to call its methods
        self.module = module
        # mqtt object
        self.gateway = None
        # track the topics subscribed
        self.topics_to_subscribe = []
        self.topics_subscribed = []
        self.topics_to_wait = []
        # queue messages while offline
        self.publish_queue = collections.deque(maxlen=300)
        # queue configuration messages while not configured
        self.configuration_queue = collections.deque(maxlen=500)
        # use a queue for exchanging incoming messages with consumer threads
        self.consumer_queue = Queue.Queue(maxsize=0)
        # number of consumer threads to create
        self.consumer_threads = 1
        # initialize consumer threads
        self.consumers = []
        for i in range(0, self.consumer_threads):
            self.consumers.append(Mqtt_consumer(i, self))
        
    # connect to the MQTT broker
    def __connect(self):
        # setup TLS for tcp transport if needed
        if self.module.gateway_ssl and self.module.gateway_transport == "tcp": 
            self.gateway.tls_set(ca_certs=self.module.gateway_ca_cert, certfile=self.module.gateway_certfile, keyfile=self.module.gateway_keyfile)
            # do not check for certificate validity
            self.gateway.tls_insecure_set(True)
        # setup SSL for websocket transport if needed
        elif self.module.gateway_ssl and self.module.gateway_transport == "websockets":
            self.gateway.tls_set(cert_reqs=ssl.CERT_NONE)
        # try to connect to the gateway until succeeding
        while self.module.connected == False:
            try:
                self.module.log_debug("Connecting to "+self.module.gateway_hostname+":"+str(self.module.gateway_port)+" ("+self.module.gateway_transport+", ssl="+str(self.module.gateway_ssl)+")")
                self.gateway.connect(self.module.gateway_hostname, self.module.gateway_port)
                # TODO: this has to be moved into on_connect but is never called if moved
                self.module.connected = True
                # TODO: last will? e.g. log a disconnecting message
            except Exception,e:
                self.module.log_warning("Unable to connect to "+self.module.gateway_hostname+":"+str(self.module.gateway_port)+" - "+exception.get(e))
                self.module.sleep(10)

    # subscribe to a given topic
    def __subscribe(self, topic):
        self.module.log_debug("Subscribing topic "+topic)
        self.gateway.unsubscribe(topic)
        self.gateway.subscribe(topic, qos=2)
        
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
        topic = self.__build_topic(house_id, self.module.fullname, to_module, command, args)
        # publish if connected
        if self.module.connected:
            info = self.gateway.publish(topic, payload, retain=retain, qos=2)
        # queue the message if offline
        else:
            self.publish_queue.append([topic, payload, retain])
            
    # unsubscribe from a topic
    def unsubscribe(self, topic):
        if topic not in self.topics_subscribed: return
        self.module.log_debug("Unsubscribing from "+topic)
        self.topics_subscribed.remove(topic)
        self.gateway.unsubscribe(topic)
    
    # called from module. Connect to the MQTT broker and subscribe to the requested topics
    def start(self):
        # set client id. Format: egeoffrey-<house_id>-<scope>-<name>
        self.__client_id = "-".join(["egeoffrey", self.module.house_id, self.module.scope, self.module.name])
        # get an instance of the MQTT client object
        if self.module.persistent_client: self.module.log_debug("Configuring as persistent mqtt client")
        clean_session = False if self.module.persistent_client else True
        self.gateway = mqtt.Client(client_id=self.__client_id, clean_session=clean_session, userdata=None, transport=self.module.gateway_transport)
        # define what to do upon connect
        def __on_connect(client, userdata, flags, rc):
            try:
                if rc == 0:
                    self.module.log_debug("Connected to "+self.module.gateway_hostname+":"+str(self.module.gateway_port))
                    # call user's callback
                    self.module.on_connect()
                    # subscribe to the requested topics
                    for topic in self.topics_to_subscribe: 
                        self.__subscribe(topic)
                        self.topics_subscribed.append(topic)
                    # if there are message in the queue, send them
                    while True:
                        try:
                            entry = self.publish_queue.popleft()
                            self.gateway.publish(entry[0], entry[1], retain=entry[2], qos=2)
                        except IndexError:
                            break
                else:
                    # unable to connect, retry
                    self.module.log_error("Cannot connect: " + mqtt.connack_string(rc))
                    self.module.connected = False
                    self.__connect()
            except Exception,e:
                self.module.log_error("runtime error in __on_connect(): "+exception.get(e))
            
        # what to do when receiving a message
        def __on_message(client, userdata, msg):
            try:
                # parse the incoming request into a message data structure
                message = Message()
                message.parse(msg.topic, msg.payload, msg.retain)
                if self.module.verbose: self.module.log_debug("Received message "+message.dump(), False)
            except Exception,e:
                self.module.log_error("Invalid message received on "+msg.topic+" - "+msg.payload+": "+exception.get(e))
                return
            # ensure this message is for this house
            if message.house_id != "*" and message.house_id != self.module.house_id:
                self.module.log_debug("received message for the wrong house "+message.house_id+": "+message.dump())
                return
            # queue the message
            try:
                queue_size = self.consumer_queue.qsize()
                # print a warning if the incoming queue is getting too big
                if queue_size > 100:
                    self.module.log_warning("the incoming message queue is getting too big ("+str(queue_size)+" messages)")
                # if really too big, there is something wrong happening, ask the watchdog to restart our module
                if queue_size > 500 and self.module.watchdog is not None:
                    self.module.log_error("the incoming message queue is too big, requesting our watchdog to restart the module")
                    self.module.watchdog.restart_module(self.module.fullname)
                    return
                # queue the message
                self.consumer_queue.put_nowait(message)
            except Exception,e:
                self.module.log_error("Unable to queue incoming message: "+exception.get(e))

        # what to do upon disconnect
        def __on_disconnect(client, userdata, rc):
            self.module.connected = False
            # call user's callback
            try: 
                self.module.on_disconnect()
            except Exception,e: 
                self.module.log_error("runtime error during on_disconnect(): "+exception.get(e))
            if rc == 0:
                self.module.log_debug("Disconnected from "+self.module.gateway_hostname+":"+str(self.module.gateway_port))
            else:
                self.module.log_warning("Unexpected disconnection, reconnecting...")
                self.__connect()
            
        # set callbacks for mqtt
        self.gateway.on_connect = __on_connect
        self.gateway.on_message = __on_message
        self.gateway.on_disconnect = __on_disconnect
        # connect to the gateway
        self.gateway.username_pw_set(self.module.house_id, password=self.module.house_passcode)
        self.__connect()
        # start loop 
        try: 
            # start message consumer threads
            for consumer in self.consumers:
                consumer.start()
            # start mqtt network thread
            self.gateway.loop_start()
        except Exception,e: 
            self.module.log_error("Unexpected runtime error: "+exception.get(e))

    # add a listener for the given request
    def add_listener(self, from_module, to_module, command, args, wait_for_it):
        topic = self.__build_topic("+", from_module, to_module, command, args)
        if wait_for_it:
            # if this is mandatory topic, unconfigure the module and add it to the list of topics to wait for
            self.topics_to_wait.append(topic)
            self.module.configured = False
            self.module.log_debug("will wait for configuration on "+topic)
        # if connected, subscribe the topic and keep track of it
        if self.module.connected: 
            if topic in self.topics_subscribed: return topic
            self.__subscribe(topic)
            self.topics_subscribed.append(topic)
        # if not connected, will subscribe once connected
        else:
            if topic in self.topics_to_subscribe: return topic
            self.topics_to_subscribe.append(topic)
        # return the topic so the user can unsubscribe from it if needed
        return topic
            
    # disconnect from the MQTT broker
    def stop(self):
        # stop all message consumer threads
        for consumer in self.consumers:
            consumer.join()
        # do nothing if not connected to the gateway
        if self.gateway == None: return
        # stop the mqtt network thread
        self.gateway.loop_stop()
        # disconnect from the gateway
        self.gateway.disconnect()
        try:
            self.module.on_disconnect()
        except Exception,e: 
            self.module.log_error("runtime error during on_disconnect(): "+exception.get(e))

