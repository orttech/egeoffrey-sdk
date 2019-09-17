# eGeoffrey SDK

Provides common functionalities for developing and running eGeoffrey modules.

## Develop

To let developers focusing on creating useful modules and beautiful contents, the eGoffrey SDK is intended to make available any capability which could be common among modules. 

Just to name only a few, the following key functionalities are provided by the SDK:
- A `Module` class which:
  - takes care of connecting to the eGeoffrey gateway
  - provides a framework of callbacks to allow developers to react upon connection, discussion, starting, stopping, etc.
  - provides common functionalities for communicating with other modules by publishing and receiving messages through the bus
  - implements local and remote logging capabilities
  - provides ad-hoc, specialized subclasses you can inherit from for each type of module and specifically:
    - A `Controller` class for controller modules
    - An `Interaction` class for interaction modules
    - A `Notification` class for notification modules which takes care of retrieving the module's configuration and receiving NOTIFY messages from the alerter so to invoke the callback `on_notify()` based on the user's configuration
    - A `Service` class for service modules which takes care of registering "push" sensors and scheduling "pull" sensors according to their configuration
- A `Message` class which abstract information exchanged between modules in a structured way
- A `Session` class which helps in keeping track of session information when communicating with other modules
- A set of utilities to manipulate strings, numbers, dates, handling exceptions, etc.

The SDK is available in both Python and Javascript.

#### Module Callbacks

When developing a new module and inhering from one of `Module`'s subclasses, the following callbacks are made available:

- `on_init()`: what to do when initializing (subclass has to implement)
- `on_connect()`: what to do just after connecting to the gateway
- `on_start()`: what to do when start running - after receiving required configuration files if any (subclass has to implement)
- `on_stop()`: what to do when shutting down (subclass has to implement)
- `on_disconnect()`: what to do just after disconnecting from the gateway
- `on_message(message)`: what to do when receiving a new message (subclass has to implement)
- `on_configuration()`: what to do when receiving a new/updated configuration (subclass has to implement)

#### Module Functions

The following functions are also provided when inhering from one of `Module`'s subclasses:

- `add_configuration_listener(args, version=None, wait_for_it=False)`: add a listener for the given configuration request (will call on_configuration())
- `add_request_listener(from_module, command, args)`: add a listener for the messages addressed to this module (will call on_message())
- `add_broadcast_listener(from_module, command, args)`: add a listener for broadcasted messages from the given module (will call on_message())
- `add_inspection_listener(from_module, to_module, command, args)`: add a listener for intercepting messages from a given module to a given module (will call on_message())
- `remove_listener(topic)`: remove a topic previously subscribed
- `send(message)`: send a message to another module
- `log_debug(text) / log_info(text) / log_warning(text) / log_error(text)`: log a message
- `is_valid_configuration(settings, configuration)`: ensure all the items of an array of settings are included in the configuration object provided
- `sleep(seconds)`: wrap around time sleep so to break if the module is stopping
- `upgrade_config(filename, from_version, to_version, content)`: upgrade a configuration file to the given version

## Build

The SDK is intended not only to facilitate the developer in re-using reliable code as a library, but also to package the outcome of his job in a more consistent way.

For this reason, SDKs are packaged in Docker images which are intended to be the base images developers use for packaging their brand new modules. 

The SDK images provide the following functionalities:
- Include already any operating system and Python requirements for running the SDK
- Set the workdir to `/egeoffrey`
- Print out the module's and the SDK's version information upon start
- Allow the developer to run custom commands before starting the eGeoffrey modules by runing `/egeoffrey/docker-init.sh`, if exists
- Start the an eGeoffrey watchdog service by running `python -m sdk.python.module.start` which will:
  - Connect to the eGeoffrey gateway by leveraging the provided `EGEOFFREY_*` environment variables
  - For any module pointed out in the `EGEOFFREY_MODULES` environment variables, load the code from its location and start the module as a thread

The SDK Docker image is based on Alpine or Raspian. 

Developers can use the one which fits best their requirements. Usually, if no Raspberry Pi specific requirements are needed (e.g. GPIO), go with the eGeoffrey SDK alpine-based image.
