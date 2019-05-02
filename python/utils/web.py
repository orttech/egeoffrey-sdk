import requests

# request a given url
def get(url,username=None,password=None,binary=False,params={},timeout=30):
	if username is not None: request = requests.get(url,params=params,auth=(username,password),timeout=timeout,verify=False)
	else: request = requests.get(url,params=params,timeout=30,verify=False)
	if binary: return request.content
	else: return request.text

