import collections
import paho.mqtt.client as mqtt
import Queue
import threading

import sdk.python.utils.exceptions as exception
from sdk.python.module.helpers.message import Message

# consumer thread which consume incoming mqtt messages
class Mqtt_consumer(threading.Thread):
    def __init__(self, index, mqtt_client):
        # call threading superclass
        super(Mqtt_consumer, self).__init__()
        # keep track of this thread index and the mqtt client
        self.index = index
        self.mqtt_client = mqtt_client
        self.running = False

    # start the consumer thread
    def run(self):
        queue = self.mqtt_client.consumer_queue
        self.running = True
        # run forever
        while self.running:
            message = None
            try:
                # get a message from the queue, waiting for maximum 1 second if empty
                message = queue.get(True, 1)
            except Exception,e: 
                # timeout exceeded, start over 
                continue
            if message is None: continue
            # consume the message
            try:
                self.on_message_consume(message)
            except Exception,e: 
                self.mqtt_client.module.log_error("runtime error during on_message_consume() - "+message.dump()+": "+exception.get(e))
            # commit message consumed
            queue.task_done()
    
    # stop the thread
    def join(self):
        self.running = False

    # dispatch a new incoming message        
    def on_message_consume(self, message):
        try:
            # identify the subscribed topic which caused this message to get here
            for pattern in self.mqtt_client.topics_subscribed:
                if mqtt.topic_matches_sub(pattern, message.topic):
                    # if the message is a configuration
                    if message.sender == "controller/config" and message.command == "CONF":
                        # TODO: this is all executed by mqtt network thread so it is blocking. Move it
                        # notify the module about the configuration just received
                        try:
                            is_valid_configuration = self.mqtt_client.module.on_configuration(message)
                        except Exception,e: 
                            self.mqtt_client.module.log_error("runtime error during on_configuration() - "+message.dump()+": "+exception.get(e))
                            return
                        # if the configuration has not been accepted by the module (returned False), ignore it
                        if is_valid_configuration is not None and not is_valid_configuration: return
                        # check if we had to wait for this message to start the module
                        configuration_consumed = False
                        if len(self.mqtt_client.topics_to_wait) > 0:
                            for req_pattern in self.mqtt_client.topics_to_wait:
                                if mqtt.topic_matches_sub(req_pattern, message.topic):
                                    self.mqtt_client.module.log_debug("received configuration "+message.topic)
                                    configuration_consumed = True
                                    self.mqtt_client.topics_to_wait.remove(req_pattern)
                                    # if there are no more topics to wait for, this service is now configured
                                    if len(self.mqtt_client.topics_to_wait) == 0: 
                                        self.mqtt_client.module.log_info("Configuration completed")
                                        # set the configured flag to true, this will cause the service to start (on_start() is in the main thread)
                                        self.mqtt_client.module.configured = True
                                        # now that is configured, if there are configuration messages waiting in the queue, deliver them
                                        while True:
                                            try:
                                                queued_message = self.mqtt_client.configuration_queue.popleft()
                                                try:
                                                    self.mqtt_client.module.on_configuration(queued_message)
                                                except Exception,e: 
                                                    self.mqtt_client.module.log_error("runtime error during on_configuration() - "+queued_message.dump()+": "+exception.get(e))
                                            except IndexError:
                                                break
                                    else:
                                        self.mqtt_client.module.log_debug("still waiting for configuration on "+str(self.mqtt_client.topics_to_wait))
                        # if this message was not consumed and the module is still unconfigured, queue it, will be delivered once configured
                        if not configuration_consumed and not self.mqtt_client.module.configured:
                            self.mqtt_client.configuration_queue.append(message)
                    # handle internal messages
                    elif message.command == "PING":
                        message.reply()
                        message.command = "PONG"
                        self.mqtt_client.module.send(message)
                    # notify the module about this message (only if fully configured)
                    else:
                        if self.mqtt_client.module.configured: 
                            try: 
                                self.mqtt_client.module.on_message(message)
                            except Exception,e: 
                                self.mqtt_client.module.log_error("runtime error during on_message(): "+exception.get(e))
                    # avoid delivering the same message multiple times for overlapping subscribers
                    return 
        except Exception,e:
            self.mqtt_client.module.log_error("Cannot handle request: "+exception.get(e))