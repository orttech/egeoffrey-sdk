# sessions for keeping track of requests
class Session():
    def __init__(self, module):
        self.__module = module
        # map request_id with session content
        self.__sessions = {}
    
    # return session's content of a given request_id
    def restore(self, message):
        request_id = message.get_request_id()
        if request_id is None: return None
        if request_id in self.__sessions:
            session = self.__sessions[request_id]
            del self.__sessions[request_id]
            return session
        else:
            self.__module.log_warning("invalid session requested "+str(request_id)+": "+message.dump())
            return None
    
    # associate the request_id of a message with a session content
    def register(self, message, session):
        request_id = message.get_request_id()
        if request_id is None: return
        self.__module.log_debug("Created session "+str(request_id)+" -> "+str(session))
        self.__sessions[request_id] = session
        return request_id
        
    # return true if this is a registered session, false otherwise
    def is_registered(self, message):
        request_id = message.get_request_id()
        if request_id is None: return False
        if request_id in self.__sessions: return True
        return False

