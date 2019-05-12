from sdk.module.module import Module

# interaction common functionalities
class Interaction(Module):
    # What to do when initializing
    def __init__(self, scope, name):
        # call superclass function
        super(Interaction, self).__init__(scope, name)
