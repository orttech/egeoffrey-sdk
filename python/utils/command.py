### Run OS commands
## DEPENDENCIES:
# OS: 
# Python: 

import Queue
import os
import threading
import subprocess

# helper class for running a command in a separate thread with a timeout
class CommandWrapper(object):
	def __init__(self, cmd, shell, background):
		self.cmd = cmd
		self.process = None
		self.shell = shell
		self.background = background
	def run(self, timeout):
		def target(queue):
			# if running in a shell, the os.setsid() is passed in the argument preexec_fn so it's run after the fork() and before  exec() to run the shell
			preexec_fn = os.setsid if self.shell else None
			# run the process
			self.process = subprocess.Popen(self.cmd, shell=self.shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=preexec_fn)
			# if running in background, just return (and discard the output)
			if self.background: return
			# read the output line by line
			for line in iter(self.process.stdout.readline,''):
				# add the line to the queue
				queue.put_nowait(str(line))
		# a queue will be used to collect the output
		queue = Queue.Queue()
		# setup the thread
		thread = threading.Thread(target=target, args=[queue])
		# start the thread
		thread.start()
		# wait for it for timeout 
		thread.join(timeout)
		if thread.is_alive():
			# if the process is still alive, terminate it
			self.process.terminate()
			# if running in a shell send the signal to all the process groups
			if self.shell: os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
			thread.join()
		# return the output
		output = ""
		if queue.qsize() == 0: return output
		try:
			# merge the lines from the queue into a single string
			while True: output = output +str(queue.get_nowait())
		except: 
			# queue is empty, return the output
			return output.rstrip()

# run a command and return the output
def run(command, shell=True, background=False):
	command = CommandWrapper(command, shell, background)
	return command.run(30)