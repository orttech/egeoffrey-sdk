

class Mqtt_client {
    constructor(module) {
        // TODO: certs
        // we need the module's object to call its methods
        this.__module = module
        // mqtt object
        this.__gateway = null;
        // track the topics subscribed
        this.__topics_to_subscribe = []
        this.__topics_subscribed = []
        this.__topics_to_wait = []
        // queue messages while offline
        this.__queue = []
    }

    // connect to the MQTT broker
    __connect() {
        var this_class = this
        var __on_connect = function(reconnect, url) {
            this_class.__module.log_info("Connected to eGeoffrey gateway "+this_class.__module.gateway_hostname+":"+this_class.__module.gateway_port)
            this_class.__module.connected = true
            this_class.__module.on_connect()
            // subscribe to the requested topics
            for (var topic of this_class.__topics_to_subscribe) {
                this_class.__subscribe(topic)
                this_class.__topics_subscribed.push(topic)
            }
            // there are message in the queue, send them
            if (this_class.__queue.length > 0) { 
                for (var entry of this_class.__queue) {
                    this_class.__gateway.send(entry[0], entry[1], 0, entry[2])
                }
                this_class.__queue = []
            }
        }
        
        // connect to the gateway
        var __on_failure = function() {
            this_class.__module.log_error("Unable to connect to "+this_class.__module.gateway_hostname+":"+this_class.__module.gateway_port)
        }
        try {
            this.__module.log_debug("Connecting to "+this.__module.gateway_hostname+":"+this.__module.gateway_port+" (ssl="+this.__module.gateway_ssl+")")
            var connect_options = {
                "userName": this.__module.house_id,
                "password": this.__module.house_passcode,
                "onSuccess": __on_connect, 
                "onFailure": __on_failure, 
                "timeout": 2, 
                "useSSL": this.__module.gateway_ssl
            }
            this.__gateway.connect(connect_options)
        } catch(e) {
            this.__module.log_error("Unable to connect to "+this.__module.gateway_hostname+":"+this.__module.gateway_port+" "+get_exception(e))
        }
    }
    
    // subscribe to a given topic
    __subscribe(topic, qos=0) {
        this.__module.log_debug("Subscribing topic "+topic)
        this.__gateway.subscribe(topic, {"qos": qos})
    }
    
    // Build the full topic (e.g. egeoffrey/v1/<house_id>/<from_module>/<to_module>/<command>/<args>)
    __build_topic(house_id, from_module, to_module, command, args) {
        if (args == "") args = "null"
        return ["egeoffrey", constants["API_VERSION"], house_id, from_module, to_module, command, args].join("/")
    }
    
    // publish payload to a given topic (queue the message while offline)
    publish(house_id, to_module, command, args, payload_data, retain=false) {
        var payload = payload_data
        if (payload != null) payload = JSON.stringify(payload)
        else {
            var buffer = new ArrayBuffer(1)
            buffer[0] = null
            payload = buffer
        }
        var topic = this.__build_topic(house_id, this.__module.fullname, to_module, command, args)
        if (this.__module.connected) this.__gateway.send(topic, payload, 0, retain=retain)
        else this.__queue.push([topic, payload, retain])
    }
    
    // unsubscribe from a topic
    unsubscribe(topic) {
        this.__module.log_debug("Unsubscribing from "+topic)
        this.__topics_subscribed.remove(topic)
        this.__gateway.unsubscribe(topic)
    }
    
    // connect to the MQTT broker and subscribed to the requested topics
    start() {
        // set client id . Format: egeoffrey-<house_id>-<scope>-<name>
        this.__client_id = ["egeoffrey", this.__module.house_id, this.__module.scope, this.__module.name].join("-")
        // get an instance of the MQTT client
        this.__gateway = new Paho.MQTT.Client(this.__module.gateway_hostname, Number(this.__module.gateway_port), this.__client_id);
        // define what to do upon connect
        var this_class = this
        var __on_connect = function(reconnect, url) {
            this_class.__module.log_debug("Connected to "+this_class.__module.gateway_hostname+":"+this_class.__module.gateway_port)
            this_class.__module.connected = true
            // subscribe to the requested topics
            for (var topic of this_class.__topics_to_subscribe) {
                this_class.__subscribe(topic)
                this_class.__topics_subscribed.push(topic)
            }
        }

        // what to do when receiving a message
        var __on_message = function(msg) {
            if (msg == null) return
            try {
                // parse the incoming request into a message data structure
                var message = new Message()
                message.parse(msg.destinationName, msg.payloadString, msg.retained)
                if (this_class.__module.verbose) this_class.__module.log_debug("Received message "+message.dump(), false)
            } catch (e) {
                this_class.__module.log_error("Invalid message received on "+msg.destinationName+" - "+msg.payloadString+": "+get_exception(e))
                return
            }
            // ensure this message is for this house
            if (message.house_id != "*" && message.house_id != this_class.__module.house_id) {
                this_class.__module.log_warning("received message for the wrong house "+message.house_id+": "+message.dump())
                return
            }
            try {
                // identify the subscribed topic which caused this message to get here
                for (var pattern of this_class.__topics_subscribed) {
                    if (topic_matches_sub(pattern, message.topic)) {
                        // if the message is a configuration
                        if (message.sender == "controller/config" && message.command == "CONF") {
                            // notify the module about the configuration just received
                            try {
                                this_class.__module.on_configuration(message)
                            } catch(e) {
                                this_class.__module.log_error("runtime error during on_configuration() - "+message.dump()+": "+get_exception(e))
                                return
                            }
                            // check if we had to wait for this to start the module
                            if (this_class.__topics_to_wait.length > 0) {
                                for (var req_pattern of this_class.__topics_to_wait) {
                                    if (topic_matches_sub(req_pattern, message.topic)) {
                                        this_class.__module.log_debug("received configuration "+message.topic)
                                        var index = this_class.__topics_to_wait.indexOf(req_pattern)
                                        this_class.__topics_to_wait.splice(index, 1)
                                        // if there are no more topics to wait for, start the module
                                        if (this_class.__topics_to_wait.length == 0) { 
                                            this_class.__module.log_debug("Configuration completed for "+this_class.__module.fullname+", starting the module...")
                                            this_class.__module.configured = true
                                            try { 
                                                this_class.__module.on_start()
                                            } catch(e) {
                                                this_class.__module.log_error("runtime error during on_start(): "+get_exception(e))
                                            }
                                        } else {
                                            this_class.__module.log_debug("still waiting for configuration on "+JSON.stringify(this_class.__topics_to_wait))
                                        }
                                    }
                                }
                            }
                        // handle internal messages
                        } else if (message.command == "PING") {
                            message.reply()
                            message.command = "PONG"
                            this_class.__module.send(message)
                        // notify the module about this message (only if fully configured)
                        } else {
                            if (this_class.__module.configured) {
                                try {
                                    this_class.__module.on_message(message)
                                } catch(e) {
                                    this_class.__module.log_error("runtime error during on_message(): "+get_exception(e))
                                }
                            }
                        }
                        // avoid delivering the same message multiple times for overlapping subscribers
                        return 
                    }
                }
            } catch(e) {
                this_class.__module.log_error("Cannot handle request: "+get_exception(e))
            }
        }

        // what to do upon disconnect
        var __on_disconnect = function(response) {
            this_class.__module.connected = false
            if (response.errorCode == 0) this_class.__module.log_debug("Disconnected from "+this_class.__module.gateway_hostname+":"+this_class.__module.gateway_port)
            else this_class.__module.log_warning("Unexpected disconnection")
            try {
                this_class.__module.on_disconnect()
            } catch(e) {
                this_class.__module.log_error("runtime error during on_disconnect(): "+get_exception(e))
            }
        }
        
        // configure callbacks
        this.__gateway.onMessageArrived = __on_message
        this.__gateway.onConnectionLost = __on_disconnect
        // connect to the gateway
        this.__connect({"userName": this.__module.house_id, "password": this.__module.house_passcode})
    }
    
    // add a listener for the given request
    add_listener(from_module, to_module, command, filter, wait_for_it) {
        var topic = this.__build_topic("+", from_module, to_module, command, filter)
        if (wait_for_it) {
            // if this is mandatory topic, unconfigure the module and add it to the list of topics to wait for
            if (wait_for_it) {
                this.__topics_to_wait.push(topic)
                this.__module.configured = false
                this.__module.log_debug("will wait for configuration on "+topic)
            }
        } 
        // subscribe the topic and keep track of it
        if (this.__module.connected) {
            if (this.__topics_subscribed.includes(topic)) return topic
            this.__subscribe(topic)
            this.__topics_subscribed.push(topic)
        }
        // if not connected, will subscribed once connected
        else {
            if (this.__topics_to_subscribe.includes(topic)) return topic
            this.__topics_to_subscribe.push(topic)
        }
        return topic
    }
    
    // disconnect from the MQTT broker
    stop() {
        if (this.__gateway == null) return
        try {
            if (this.__gateway.isConnected()) {
                this.__gateway.disconnect()
                try {
                    this.__module.on_disconnect()
                } catch(e) {
                    this_class.__module.log_error("runtime error during on_disconnect(): "+get_exception(e))
                }
            }
            this.__module.connected = false
        } catch(e) {
            this.__module.log_error("Unable to disconnect from "+this.__module.gateway_hostname+":"+this.__module.gateway_port+" "+get_exception(e))
        }
    }
}