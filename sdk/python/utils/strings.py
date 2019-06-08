### Strings utilities
## DEPENDENCIES:
# OS: 
# Python: 

from datetime import datetime

# truncate a long string 
def truncate(string, max_len=50):
    if string is None: string = ""
    string = str(string)
    return (string[:max_len] + '...') if len(string) > max_len else string
    
# convert a hex string into a ascii string
def hex2string(hex):
    try:
        string = hex.decode("hex")
        return string
    except: return None

# format a log line for printing
def format_log_line(severity, module, text):
    severity = str(severity.upper())
    if severity == "WARNING": severity = "\033[93mWARNING\033[0m"
    elif severity == "ERROR": severity = "\033[91mERROR\033[0m"
    return "["+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"]["+str(module)+"] "+severity+ ": "+truncate(str(text), 2000)