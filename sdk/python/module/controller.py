from sdk.python.module.module import Module

# controller common functionalities
class Controller(Module):
    # What to do when initializing
    def __init__(self, scope, name):
        # call superclass function
        super(Controller, self).__init__(scope, name)
