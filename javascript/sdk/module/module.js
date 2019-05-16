

// Module class from which all the components inherits common functionalities
class Module {
    constructor(scope, name) {
        // set name of this module
        this.scope = scope
        this.name = name
        this.fullname = scope+"/"+name
        // module version
        this.version = constants.VERSION
        this.build = null
        // gateway settings
        this.gateway_hostname = "MYHOUSE_GATEWAY_HOSTNAME" in window ? window.MYHOUSE_GATEWAY_HOSTNAME : "localhost"
        this.gateway_port = "MYHOUSE_GATEWAY_PORT" in window ? window.MYHOUSE_GATEWAY_PORT : 443
        this.gateway_ssl = "MYHOUSE_GATEWAY_SSL" in window ? Boolean(window.MYHOUSE_GATEWAY_SSL) : false
        // house settings
        this.house_id = "MYHOUSE_ID" in window ? window.MYHOUSE_ID : "default_house"
        this.house_passcode = "MYHOUSE_PASSCODE" in window ? window.MYHOUSE_PASSCODE : ""
        // debug
        this.debug = "MYHOUSE_DEBUG" in window ? Boolean(window.MYHOUSE_DEBUG) : 0
        this.verbose = "MYHOUSE_VERBOSE" in window ? Boolean(window.MYHOUSE_VERBOSE) : 0
        // logging
        this.logging_remote = "MYHOUSE_LOGGING_REMOTE" in window ? Boolean(window.MYHOUSE_LOGGING_REMOTE) : false
        this.logging_local = "MYHOUSE_LOGGING_LOCAL" in window ? Boolean(window.MYHOUSE_LOGGING_LOCAL) : true
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
    add_configuration_listener(args, wait_for_it=false) {
        return this.__mqtt.add_listener("controller/config", "*/*", "CONF", args, wait_for_it)
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
        if (message.sender == "" || message.recipient == "") {
            this.log_warning("invalid message to send", false)
            return 
        }
        // publish it to the message bus
        var payload
        if (message.is_null) payload = null
        else payload = message.get_payload()
        this.__mqtt.publish(message.recipient, message.command, message.args, payload, message.retain)
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
    __is_valid_configuration(settings, configuration) {
        if (configuration.constructor != Object) return false
        for (var item of settings) {
            if (! (item in configuration) || configuration[item] == null) { 
                this.log_warning("Invalid configuration received, "+item+" missing in "+JSON.stringify(configuration))
                return false
            }
        }
        return true
    }
    
    // ensure the configuration provided contains all the required settings, if not, unconfigure the module
    is_valid_module_configuration(settings, configuration) {
        return this.__is_valid_configuration(settings, configuration)
    }

    // ensure the configuration provided contains all the required settings
    is_valid_configuration(settings, configuration) {
        return this.__is_valid_configuration(settings, configuration)
    }
    
    // run the module, called when starting the thread
    run() {
        var build = this.build != null ? " (build "+this.build+")" : ""
        this.log_info("Starting module v"+this.version+build)
        // connect to the mqtt broker
        this.__mqtt.start()
        // subscribe to any request addressed to this module  
        this.add_request_listener("+/+", "+", "#")
        // subscribe to any configuration aimed for this module  
        this.add_configuration_listener(this.fullname)
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