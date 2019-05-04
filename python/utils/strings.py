### Strings utilities
## DEPENDENCIES:
# OS: 
# Python: 

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