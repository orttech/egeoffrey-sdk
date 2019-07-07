### Date/time utilities
## DEPENDENCIES:
# OS: 
# Python: 

import datetime
import time

class DateTimeUtils():
    def __init__(self, utc_offset):
        self.__utc_offset = utc_offset
        
    # return the timestamp with the timezone offset applied
    def timezone(self, timestamp):
        return int(timestamp+self.__utc_offset*3600)

    # return an UTC timestamp from a local timezone timestamp
    def utc(self, timestamp):
        return int(timestamp-self.__utc_offset*3600)
        
    # return the now timestamp (in the current timezone)
    def now(self):
        return self.timezone(int(time.time()))

    # return yesterday's timestamp (in the local timezone)
    def yesterday(self):
        return self.now()-24*3600

    # return the last hour timestamp (in the local timezone)
    def last_hour(self):
        return self.now()-60*60
        
    # generate a given timestamp based on the input
    def get_timestamp(self, years, months, days, hours, minutes, seconds):
        date = datetime.datetime(years, months, days, hours, minutes, seconds, 0)
        return int((date - datetime.datetime(1970, 1, 1)).total_seconds())

    # return day start timestamp
    def day_start(self, timestamp):
        date = datetime.datetime.utcfromtimestamp(timestamp)
        return self.get_timestamp(date.year, date.month, date.day, 0, 0, 0)
        
    # return day end timestamp
    def day_end(self, timestamp):
        date = datetime.datetime.utcfromtimestamp(timestamp)
        return self.get_timestamp(date.year, date.month, date.day, 23, 59, 59)

    # return hour start timestamp
    def hour_start(self, timestamp):
        date = datetime.datetime.utcfromtimestamp(timestamp)
        return self.get_timestamp(date.year, date.month, date.day, date.hour, 0, 0)

    # return hour end timestamp
    def hour_end(self, timestamp):
        date = datetime.datetime.utcfromtimestamp(timestamp)
        return self.get_timestamp(date.year, date.month, date.day, date.hour, 59, 59)
        
    # return a timestamp as a human readable format
    def timestamp2date(self, timestamp):
        return datetime.datetime.utcfromtimestamp(self.utc(int(timestamp))).strftime('%Y-%m-%d %H:%M:%S')
