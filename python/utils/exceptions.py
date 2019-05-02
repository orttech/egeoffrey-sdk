import sys
import traceback

# return the exception as a string
def get(e):
	etype, value, tb = sys.exc_info()
	error = ''.join(traceback.format_exception(etype, value, tb,None))
	return error.replace('\n','|')