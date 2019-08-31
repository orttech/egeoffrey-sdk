### job scheduler
## DEPENDENCIES:
# OS: 
# Python: APScheduler

import logging
import apscheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor

# TODO: use this class for all modules
# log to MQTT
class MQTTLogHandler(logging.StreamHandler):
    def __init__(self, module):
        super(MQTTLogHandler,self).__init__()
        self.__module = module
    def emit(self, record):
        if record.levelname.lower() == "debug": self.__module.log_debug(self.format(record))
        if record.levelname.lower() == "info": self.__module.log_info(self.format(record))
        if record.levelname.lower() == "warning": self.__module.log_warning(self.format(record))
        if record.levelname.lower() == "error": self.__module.log_error(self.format(record))
        if record.levelname.lower() == "critical": self.__module.log_error(self.format(record))

class Scheduler():
    def __init__(self, module, size="small"):
        self.__module = module
        self.__started = False
        # default values for each job (30s tolerance to avoid missed job and put together multiple queued jobs)
        self.__job_defaults = {
            "coalesce": True,
            "misfire_grace_time": 30
        }
        self.__executors = {}
        # increase the thread pool executor to 20 for large schedulers
        if size =="large":
            self.__executors = {
                "default": ThreadPoolExecutor(20),
                "processpool": ProcessPoolExecutor(10)
            }
        # create the scheduler which will run each job in background
        self.__scheduler = BackgroundScheduler(job_defaults=self.__job_defaults, executors=self.__executors)
        # setup logging
        self.__setup_logger("apscheduler.executors.default")
        self.__setup_logger("apscheduler.scheduler")

    # setup the given scheduler logger
    def __setup_logger(self, logger):
        logger = logging.getLogger(logger)
        logger.setLevel(logging.CRITICAL)
        handler = MQTTLogHandler(self.__module)
        handler.setLevel(logging.CRITICAL)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        
    # return the scheduler event name from an id
    def __get_event_name(self, code):
        if code == apscheduler.events.EVENT_SCHEDULER_STARTED: return "EVENT_SCHEDULER_STARTED"
        elif code == apscheduler.events.EVENT_SCHEDULER_SHUTDOWN: return "EVENT_SCHEDULER_SHUTDOWN"
        elif code == apscheduler.events.EVENT_SCHEDULER_PAUSED: return "EVENT_SCHEDULER_PAUSED"
        elif code == apscheduler.events.EVENT_SCHEDULER_RESUMED: return "EVENT_SCHEDULER_RESUMED"
        elif code == apscheduler.events.EVENT_EXECUTOR_ADDED: return "EVENT_EXECUTOR_ADDED"
        elif code == apscheduler.events.EVENT_EXECUTOR_REMOVED: return "EVENT_EXECUTOR_REMOVED"
        elif code == apscheduler.events.EVENT_JOBSTORE_ADDED: return "EVENT_JOBSTORE_ADDED"
        elif code == apscheduler.events.EVENT_JOBSTORE_REMOVED: return "EVENT_JOBSTORE_REMOVED"
        elif code == apscheduler.events.EVENT_ALL_JOBS_REMOVED: return "EVENT_ALL_JOBS_REMOVED"
        elif code == apscheduler.events.EVENT_JOB_ADDED: return "EVENT_JOB_ADDED"
        elif code == apscheduler.events.EVENT_JOB_REMOVED: return "EVENT_JOB_REMOVED"
        elif code == apscheduler.events.EVENT_JOB_MODIFIED: return "EVENT_JOB_MODIFIED"
        elif code == apscheduler.events.EVENT_JOB_SUBMITTED: return "EVENT_JOB_SUBMITTED"
        elif code == apscheduler.events.EVENT_JOB_MAX_INSTANCES: return "EVENT_JOB_MAX_INSTANCES"
        elif code == apscheduler.events.EVENT_JOB_EXECUTED: return "EVENT_JOB_EXECUTED"
        elif code == apscheduler.events.EVENT_JOB_ERROR: return "EVENT_JOB_ERROR"
        elif code == apscheduler.events.EVENT_JOB_MISSED: return "EVENT_JOB_MISSED"
        elif code == apscheduler.events.EVENT_ALL: return "EVENT_ALL"
        else: return "UNKNOWN"
        
    # return well formatted log scheduler errors
    def __handle_error(self, code,event):
        job = self.__scheduler.get_job(event.job_id)
        job_text = str(job.func_ref)+str(job.args) if job is not None else ""
        msg = self.__get_event_name(code)+" for scheduled task "+job_text+": "
        if event.exception:
            msg = msg + "Exception "
            msg = msg +''.join(event.traceback)
            msg = msg.replace('\n','|')
            msg = msg + ": "+str(event.exception)
        else: 
            msg = msg + "No exception available"
        self.__module.log_error(msg)
        
    # handle errors and exceptions   
    def __on_job_missed(self, event):
        self.__handle_error(apscheduler.events.EVENT_JOB_MISSED, event)
        
    # handle scheduler errors
    def __on_job_error(self, event): 
        self.__handle_error(apscheduler.events.EVENT_JOB_ERROR,event)
    
    # start the scheduler
    def start(self):
        if not self.__started:
            # listen for errors
            self.__scheduler.add_listener(self.__on_job_missed, apscheduler.events.EVENT_JOB_MISSED)
            self.__scheduler.add_listener(self.__on_job_error, apscheduler.events.EVENT_JOB_ERROR)
            # start the scheduler
            self.__scheduler.start()
            self.__started = True
        
    # stop the scheduler
    def stop(self):
        if self.__started: 
            self.__scheduler.shutdown()
            self.__started = False
    
    # add a job (dictionary with all the settings) to the scheduler
    def add_job(self, job):
        # start the scheduler if not running
        if not self.__started: self.start()
        # add the new job
        return self.__scheduler.add_job(**job)
        
    # remove a job (by id) from the scheduler
    def remove_job(self, id):
        return self.__scheduler.remove_job(id)
