from sdk.module.module import Module
from sdk.module.helpers.cache import Cache

# service common functionalities
class Service(Module):
    # What to do when initializing
    def __init__(self, scope, name):
        # call superclass function
        super(Service, self).__init__(scope, name)
        # initialize internal cache
        self.cache = Cache()