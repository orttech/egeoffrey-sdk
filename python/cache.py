import time

# in memory cache helper class
class Cache():
    def __init__(self):
        self.__cache = {}
        
    # add key=value in the cache and set expiration time in seconds
    def add(self, key, value, expire=60):
        self.__cache[key] = {}
        self.__cache[key]["timestamp"] = int(time.time())
        self.__cache[key]["expire"] = expire
        self.__cache[key]["value"] = value
    
    # check if key is in the cache and not expired
    def find(self, key):
        if key in self.__cache and int(time.time()) - self.__cache[key]["timestamp"] < self.__cache[key]["expire"]: 
            return True
        return False
    
    # get value associated to key from the cache
    def get(self, key):
        if key in self.__cache: return self.__cache[key]["value"]