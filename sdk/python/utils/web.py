### Web requests utilities
## DEPENDENCIES:
# OS: 
# Python: 

import requests
from urllib3.exceptions import InsecureRequestWarning
# Suppress only the single warning from urllib3 needed
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# request a given url
def get(url,username=None,password=None,binary=False,params={},timeout=30):
	if username is not None: request = requests.get(url, params=params, auth=(username,password), timeout=timeout, verify=False)
	else: request = requests.get(url, params=params, timeout=30, verify=False)
	if binary: return request.content
	else: return request.text

