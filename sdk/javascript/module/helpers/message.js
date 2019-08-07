
// representation of a message to be sent to the bus
class Message {
    constructor(module=null) {
        this.reset()
        // if module is given, set module name as sender and associated house_id
        if (module != null) {
            this.sender = module.fullname
            this.house_id = module.house_id
        }
    }
    
    // generate and set a request_id
    __add_request_id() {
        var min = 1; 
        var max = 100000;
        this.__payload["request_id"] = Math.floor(Math.random() * (+max - +min)) + +min; 
    }
    
    // clone an object
    __clone(object) {
        return JSON.parse(JSON.stringify(object))
    }
    
    // reset the message
    reset() {
        // topic from which the message comes from, populated only for incoming messages
        this.topic = ""
        // house id
        this.house_id = ""
        // sender module
        this.sender = ""
        // recipient module
        this.recipient = ""
        // requested command to execute
        this.command = ""
        // arguments of the command
        this.args = ""
        // version of the configuration file
        this.config_schema = null
        // setup the payload (not directly accessible by the user)
        this.__payload = {}
        this.clear()
        // set to true when payload is null
        this.is_null = false
        // retain the message in the mqtt bus
        this.retain = false
    }
        
    // clear the payload only
    clear() {
        // content of the message made up of a unique request_id and user's data
        this.__payload = {
            "request_id": 0,
            "data": {}
        }
        this.__add_request_id()
    }
    
    // parse MQTT message (topic and payload)
    parse(topic, payload, retain) {
        var topics = topic.split("/")
        // sanity check
        if (topics.legth  < 8) throw "missing required information in topic"
        if (topics[0] != "eGeoffrey" || topics[1] != constants["API_VERSION"]) throw "invalid api call"
        this.topic = topic
        this.house_id = topics[2]
        this.sender = topics[3]+"/"+topics[4]
        this.recipient = topics[5]+"/"+topics[6]
        this.command = topics[7]
        this.retain = retain
        this.args = topics.slice(8, topics.length).join("/")
        // parse configuration version if any
        if (this.command == "CONF") {
            var match = this.args.match(/^(\d)\/(.+)$/)
            if (match == null) throw "configuration version is missing from configuration file "+this.args
            this.config_schema = parseInt(match[1], 10)
            this.args = match[2]
        }
        // null payload (for clearing retain flag)
        if (payload == null) this.is_null = true
        else {
            // expecting a json payload
            try {
                this.__payload = JSON.parse(payload)
            } catch(e) {
                throw "payload in an invalid json format"
            }
        }
    }

    // set the payload to value
    set_data(value) {
        this.__payload["data"] = value
    }
    
    // set key of the payload to value
    set(key, value) {
        if (this.__payload["data"].constructor != Object) this.__payload["data"] = {}
        this.__payload["data"][key] = value
    }
    
    // set the payload to null
    set_null() {
        this.is_null = true
        this.__payload = null
    }
    
    // get the value of key of the payload
    get(key) {
        if (this.is_null) return null
        if (this.__payload["data"].constructor != Object) return null
        if (! ("data" in this.__payload)) return null
        if (! (key in this.__payload["data"])) return null
        return this.__clone(this.__payload["data"][key])
    }
    
    // return true if payload has the given key
    has(key) {
        if (this.get(key) == null) return false
        return true
    }
    
    // get the value of the payload
    get_data() {
        if (! ("data" in this.__payload)) return null
        // return a clone of the data
        return this.__clone(this.__payload["data"])
    }
    
    // get the request_id
    get_request_id() {
        if (! ("request_id" in this.__payload)) return null
        return this.__payload["request_id"]
    }
    
    // get the payload (not supposed to be called by users
    get_payload() {
        return this.__payload
    }
    
    // reply to this message
    reply() {
        // swap sender and recipient
        var tmp = this.sender 
        this.sender = this.recipient
        this.recipient = tmp
        // clear the content (while keeping original command and args)
        this.topic = "" 
        this.__payload["data"] = {}
    }
    
    // forward this message to another module
    forward(recipient) {
        // new sender is the current recipient
        this.sender = this.recipient
        // set the recipient to the provided one
        this.recipient = recipient
        this.topic = ""
    }
    
    // dump the content of this message
    dump() {
        var content
        if (this.is_null) content = "null"
        else content = JSON.stringify(this.__payload["data"])+" ["+this.__payload["request_id"]+"]"
        var version = this.config_schema != null ? "v"+this.config_schema : ""
        return "Message("+this.sender+" -> "+this.recipient+": "+this.command+" "+this.args+" "+version+": "+content+")"
    }
}