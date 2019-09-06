import datetime

from sdk.python.module.module import Module
from sdk.python.module.helpers.cache import Cache
from sdk.python.module.helpers.scheduler import Scheduler
from sdk.python.module.helpers.message import Message

import sdk.python.utils.numbers
import sdk.python.utils.exceptions as exception

# service common functionalities
class Service(Module):
    # What to do when initializing
    def __init__(self, scope, name):
        # call superclass function
        super(Service, self).__init__(scope, name)
        # initialize internal cache
        self.cache = Cache()
        # scheduler is needed for polling sensors
        self.__scheduler = Scheduler(self)
        # map sensor_id with scheduler job_id
        self.__jobs = {}
        # map sensor_id with service's configuration
        self.sensors = {}
        # request all sensors' configuration so to filter sensors of interest
        self.add_configuration_listener("sensors/#", 1)
        
    # function to run when scheduling a job
    def __poll_sensor(self, sensor_id, configuration):
        # simulate a message from the hub to trigger the sensor
        message = Message(self)
        message.sender = "controller/hub"
        message.recipient = self.fullname
        message.command = "IN"
        message.args = sensor_id
        message.set_data(configuration)
        self.on_message(message)

    # unschedule a job
    def __remove_schedule(self, sensor_id):
        # if already scheduled, stop it
        if sensor_id in self.__jobs:
            try:
                self.__scheduler.remove_job(self.__jobs[sensor_id])
            except Exception,e: 
                self.log_error("Unable to remove scheduled job for sensor "+sensor_id+": "+exception.get(e))
        
    # schedule a job for polling a sensor
    def __add_schedule(self, sensor_id, schedule, configuration):
        # clean it up first
        self.__remove_schedule(sensor_id)
        # "schedule" contains apscheduler settings for this sensor
        job = schedule
        # add extra-delay picked randomly in a [-10,+20] seconds window
        job["jitter"] = 10
        # add function to call and args
        job["func"] = self.__poll_sensor
        job["args"] = [sensor_id, configuration]
        # schedule the job for execution
        try:
            self.__jobs[sensor_id] = self.__scheduler.add_job(job).id
        except Exception,e: 
            self.log_error("Unable to scheduled job for sensor "+sensor_id+": "+exception.get(e))
        # run the job immediately
        poll_now_job = {}
        poll_now_job["trigger"] = "date"
        poll_now_job["run_date"] = datetime.datetime.now() + datetime.timedelta(seconds=sdk.python.utils.numbers.randint(5,20))
        poll_now_job["func"] = self.__poll_sensor
        poll_now_job["args"] = [sensor_id, configuration]
        self.__scheduler.add_job(poll_now_job)

    # register an pull/push sensor
    def register_sensor(self, message, validate=[]):
        sensor_id = message.args.replace("sensors/","")
        sensor = message.get_data()
        # a sensor has been added/updated, filter in only relevant sensors
        if "service" not in sensor or sensor["service"]["name"] != self.name: return
        if "disabled" in sensor and sensor["disabled"]: return
        service = message.get("service")
        if not self.is_valid_configuration(["configuration"], service): return
        # in pull mode we need to schedule sensor's polling
        if service["mode"] == "pull":
            # for pull sensors we need a schedule
            if not self.is_valid_configuration(["schedule"], service): return
            # schedule for polling the sensor
            self.log_debug("Scheduling "+sensor_id+" polling at "+str(service["schedule"])+" with configuration "+str(service["configuration"]))
            self.__add_schedule(sensor_id, service["schedule"], service["configuration"])
        # in push mode the sensor will unsolicited generate new measures
        elif service["mode"] == "push":
            if not self.is_valid_configuration(validate, service["configuration"]): return
            self.log_info("registered push sensor "+sensor_id+" with configuration "+str(service["configuration"]))
        # keep track of the sensor's configuration
        self.sensors[sensor_id] = service["configuration"]
        return sensor_id

    # unregister a sensor
    def unregister_sensor(self, message):
        sensor_id = message.args.replace("sensors/","")
        # a sensor has been deleted
        if sensor_id in self.sensors:
            del self.sensors[sensor_id]
            # remove scheduler if pull sensor
            if sensor_id in self.__jobs:
                self.__remove_schedule(sensor_id)
        return sensor_id