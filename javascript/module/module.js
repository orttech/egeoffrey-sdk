

// Module class from which all the components inherits common functionalities
class Module {
    constructor(scope, name) {
        // set name of this module
        this.scope = scope
        this.name = name
        this.fullname = scope+"/"+name
        // module version
        this.version = null
        this.build = null
        // gateway settings
        this.gateway_hostname = "EGEOFFREY_GATEWAY_HOSTNAME" in window ? window.EGEOFFREY_GATEWAY_HOSTNAME : "localhost"
        this.gateway_port = "EGEOFFREY_GATEWAY_PORT" in window ? window.EGEOFFREY_GATEWAY_PORT : 443
        this.gateway_ssl = "EGEOFFREY_GATEWAY_SSL" in window ? Boolean(window.EGEOFFREY_GATEWAY_SSL) : false
        // house settings
        this.house_id = "EGEOFFREY_ID" in window ? window.EGEOFFREY_ID : "default_house"
        this.house_passcode = "EGEOFFREY_PASSCODE" in window ? window.EGEOFFREY_PASSCODE : ""
        // debug
        this.debug = "EGEOFFREY_DEBUG" in window ? Boolean(window.EGEOFFREY_DEBUG) : 0
        this.verbose = "EGEOFFREY_VERBOSE" in window ? Boolean(window.EGEOFFREY_VERBOSE) : 0
        // logging
        this.logging_remote = "EGEOFFREY_LOGGING_REMOTE" in window ? Boolean(window.EGEOFFREY_LOGGING_REMOTE) : false
        this.logging_local = "EGEOFFREY_LOGGING_LOCAL" in window ? Boolean(window.EGEOFFREY_LOGGING_LOCAL) : true
        // status
        this.connected = false
        this.configured = true // by default no configuration is required to start
        this.stopping = false
        // initialize mqtt client for connecting to the bus
        this.__mqtt = new Mqtt_client(this)
        // initialize session manager
        this.sessions = new Session(this)
        // call module implementation of init
        try {
            this.log_debug("Initializing module...")
            this.on_init()
        } catch(e) {
            this.log_error("runtime error during on_init(): "+get_exception(e))
        }
        
    }
    // Add a listener for the given configuration request (will call on_configuration())
    add_configuration_listener(args, version=null, wait_for_it=false) {
        var filename = version == null ? args : version+"/"+args
        return this.__mqtt.add_listener("controller/config", "*/*", "CONF", filename, wait_for_it)
    }
    
    // add a listener for the messages addressed to this module (will call on_message())
    add_request_listener(from_module, command, args) {
        return this.__mqtt.add_listener(from_module, this.fullname, command, args, false)
    }
    
    // add a listener for broadcasted messages from the given module (will call on_message())
    add_broadcast_listener(from_module, command, args) {
        return this.__mqtt.add_listener(from_module, "*/*", command, args, false)
    }
    
    // add a listener for intercepting messages from a given module to a given module (will call on_message())
    add_inspection_listener(from_module, to_module, command, args) {
        return this.__mqtt.add_listener(from_module, to_module, command, args, false)
    }
    
    // remove a topic previously subscribed
    remove_listener(topic) {
        this.__mqtt.unsubscribe(topic)
    }
        
    // send a message to another module
    send(message) {
        if (this.verbose) this.log_debug("Publishing message "+message.dump(), false)
        // ensure message is valid
        if (message.sender == "" || message.sender == "*/*" || message.recipient == "" || message.command == "" || message.house_id == "") {
            this.log_warning("invalid message to send: "+message.dump(), false)
            return 
        }
        // prepare config version if any
        if (message.config_schema != null) message.args = message.config_schema+"/"+message.args
        // prepare payload
        var payload
        if (message.is_null) payload = null
        else payload = message.get_payload()
        // publish it to the message bus
        this.__mqtt.publish(message.house_id, message.recipient, message.command, message.args, payload, message.retain)
    }

    // log a message
    __log(severity, text, allow_remote_logging) {
        if (this.logging_local) console.log(format_log_line(severity, this.fullname, text))
        if (this.logging_remote && allow_remote_logging) {
            // send the message to the logger module
            message = Message(this)
            message.recipient = "controller/logger"
            message.command = "LOG"
            message.args = severity
            message.set_data(text)
            this.send(message)
        }
    }

    // handle debug logs
    log_debug(text, allow_remote_logging=true) {
        if (this.debug == 0) return
        this.__log("debug", text, allow_remote_logging)
    }
    
    // handle info logs
    log_info(text, allow_remote_logging=true) {
        this.__log("info", text, allow_remote_logging)
    }        

    // handle warning logs
    log_warning(text, allow_remote_logging=true) {
        this.__log("warning", text, allow_remote_logging)
    }
    
    // handle error logs
    log_error(text, allow_remote_logging=true) {
        this.__log("error", text, allow_remote_logging)
    }
    
    // ensure all the items of the array of settings are included in the configuration object provided
    is_valid_configuration(settings, configuration) {
        for (var item of settings) {
            if (! (item in configuration) || configuration[item] == null) { 
                this.log_warning("Invalid configuration received, "+item+" missing in "+JSON.stringify(configuration))
                return false
            }
        }
        return true
    }
    
    // upgrade a configuration file to the given version
    upgrade_config(filename, from_version, to_version, content) {
        // delete the old configuration file first
        message = Message(self)
        message.recipient = "controller/config"
        message.command = "DELETE"
        message.args = filename
        message.config_schema = from_version
        this.send(message)
        // save the new version
        message = Message(self)
        message.recipient = "controller/config"
        message.command = "SAVE"
        message.args = filename
        message.config_schema = to_version
        message.set_data(content)
        this.send(message)
        this.log_info("Requesting to upgrade configuration "+filename+" from v"+from_version+" to v"+to_version)
    }
    
    // run the module, called when starting the thread
    run() {
        this.log_info("Starting module")
        // connect to the mqtt broker
        this.__mqtt.start()
        // subscribe to any request addressed to this module  
        this.add_request_listener("+/+", "+", "#")
        // run the user's callback if configured, otherwise will be started once all the required configuration will be received
        if (this.configured) {
            try {
                this.on_start()
            } catch(e) { 
                this.log_error("runtime error during on_start(): "+get_exception(e))
            }
        }
    }
    
    // shut down the module, called when stopping the thread
    join() {
        this.log_info("Stopping module...")
        this.stopping = true
        try {
            this.on_stop()
        } catch(e) { 
                this.log_error("runtime error during on_stop(): "+get_exception(e))
        }
        this.__mqtt.stop()
    }
    
    // What to do when initializing (subclass has to implement)
    on_init() {
        throw new Error('on_init() not implemented')
    }
    
    // What to do just after connecting (subclass may implement)
    on_connect() {
    }
        
    // What to do when running (subclass has to implement)
    on_start() {
        throw new Error('on_start() not implemented')
    }
        
    // What to do when shutting down (subclass has to implement)
    on_stop() {
        throw new Error('on_stop() not implemented')
    }
    
    // What to do just after disconnecting (subclass may implement)
    on_disconnect() {
    }

    // What to do when receiving a request for this module (subclass has to implement)
    on_message(message) {
        throw new Error('on_message() not implemented')
    }

     // What to do when receiving a new/updated configuration for this module (subclass has to implement)
    on_configuration() {
        throw new Error('on_configuration() not implemented')
    }
}