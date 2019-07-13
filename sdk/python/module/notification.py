import time
import Queue
from abc import ABCMeta, abstractmethod

from sdk.python.module.module import Module

import sdk.python.utils.exceptions as exception

# notification common functionalities
class Notification(Module):
    # used for enforcing abstract methods
    __metaclass__ = ABCMeta 
    
    # What to do when initializing
    def __init__(self, scope, name):
        # call superclass function
        super(Notification, self).__init__(scope, name)
        # module's configuration
        self.config = {}
        # count number of notifications
        self.__counter = 0
        # keep track of the current hour
        self.__current_hour = None
        # queue notifications
        self.__queue = Queue.Queue(10)
        self.__playing = False
        # request required configuration files
        self.add_configuration_listener(self.fullname, True)
        self.add_broadcast_listener("controller/alerter", "NOTIFY", "#")
    
    # filter notification
    def __filter_notification(self, severity, text):
        # if there is a filter on the notification, apply it
        if "suppress" in self.config:
            configuration = self.config["suppress"]
            # TODO: apply timezone
            # retrieve the current hour
            hour = int(time.strftime("%H"))
            # if this is a new hour, reset the notification counters
            if hour is None or self.__current_hour != hour:
                self.__counter = 0
                self.__current_hour = hour
            # initialize
            mute_override = False
            severity_below = None
            timeframe_severity_exception = None
            # ensure the severity is equals or above the minimum severity configured
            if "severity_below" in configuration:
                severity_below = configuration["severity_below"]
                if severity_below == "warning" and severity in ["info"]: return
                elif severity_below == "alert" and severity in ["info", "warning"]: return
            # check if the notification is severe enough to override the mute setting
            if "timeframe_severity_exception" in configuration:
                timeframe_severity_exception = configuration["timeframe_severity_exception"]
                if timeframe_severity_exception == "warning" and severity in ["warning", "alert"]: mute_override = True
                elif timeframe_severity_exception == "alert" and severity in ["alert"]: mute_override = True
            # ensure the channel is not mute now
            if "timeframe" in configuration and "-" in configuration["timeframe"] and not mute_override:
                timeframe = configuration["timeframe"].split("-")
                if len(timeframe) != 2: return
                timeframe[0] = int(timeframe[0])
                timeframe[1] = int(timeframe[1])
                # e.g. 08-12
                if timeframe[0] < timeframe[1] and (hour >= timeframe[0] and hour < timeframe[1]): return
                # e.g. 20-07
                if timeframe[0] > timeframe[1] and (hour >= timeframe[0] or hour < timeframe[1]): return
            # check if rate limit is configured and we have not exceed the numner of notifications during this hour
            if "rate_hour" in configuration and configuration["rate_hour"] != 0 and self.__counter >= configuration["rate_hour"]: return
            # increase the counter
            self.__counter = self.__counter + 1
            if "rate_hour" in configuration: self.log_debug("notification #"+str(self.__counter)+" for hour "+str(self.__current_hour)+":00")
        # play the notification
        self.__notify(severity, text)
    
    # run the notification by calling the implementation of on_notify()
    def __notify(self, severity, text):
        # another notification is already in progress, queue it
        if self.__playing:
            self.log_debug("queuing notification about "+text)
            self.__queue.put([severity, text])
        # play the notification
        else:
            self.__playing = True
            try: 
                self.on_notify(severity, text)
            except Exception,e:
                self.log_error("unable to notify: "+exception.get(e))
            self.__playing = False
            # if there is a notification in the queue, spool it
            if self.__queue.qsize() > 0:
                entry = self.__queue.get()
                self.__notify(entry[0], entry[1])
                

    # What to do when receiving a request for this module
    def on_message(self, message):
        if not self.configured: return
        if "disabled" in self.config and self.config["disabled"]: return
        # capture notifications from alerter
        if message.sender == "controller/alerter" and message.command == "NOTIFY":
            split = message.args.split("/")
            self.__filter_notification(split[0], message.get_data())
        # run the notification on demand
        if message.command == "RUN":
            self.__notify(message.args, message.get_data())

    # What to do when ask to notify (subclass has to implement)
    @abstractmethod
    def on_notify(self, severity, text):
        pass
