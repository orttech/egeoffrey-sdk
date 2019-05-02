
// sessions for keeping track of requests
class Session {
    constructor(module) {
        this.__module = module
        // map request_id with session content
        this.__sessions = {}
    }
    
    // return session's content of a given request_id
    restore(message) {
        var request_id = message.get_request_id()
        if (request_id == null) return null
        if (request_id in this.__sessions) {
            var session = this.__sessions[request_id]
            delete this.__sessions[request_id]
            return session
        } else {
            this.__module.log_warning("invalid session requested "+request_id+": "+message.dump())
            return null
        }
    }
    
    // associate the request_id of a message with a session content
    register(message, session) {
        var request_id = message.get_request_id()
        if (request_id == null) return null
        this.__module.log_debug("Created session "+request_id+" -> "+JSON.stringify(session))
        this.__sessions[request_id] = session
        return request_id
    }
    
    // return true if this is a registered session, false otherwise
    is_registered(message) {
        request_id = message.get_request_id()
        if (request_id == null) return false
        if (request_id in this.__sessions) return true
        return false
    }
}