### Number utilities
## DEPENDENCIES:
# OS: 
# Python: tinynumpy

from tinynumpy import tinynumpy
import random
import __builtin__

# return true if the input is a number
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
        
# normalize the value. If the input is a number, keep a single digit, otherwise return a string
def normalize(value, format=None):
    if format == "image" or format == "calendar" or format == "position": return value
    if value == "None": return "None"
    if format is None:
        return float("{0:.1f}".format(float(value))) if is_number(value) else str(value)
    elif format == "int": return int(float(value))
    elif format == "float_1": return float("{0:.1f}".format(float(value)))
    elif format == "float_2": return float("{0:.2f}".format(float(value)))
    else: return str(value)

# remove all occurences of value from array
def remove_all(array, value_array):
    return [x for x in array if x not in value_array]
        
# calculate the min of a given array of data
def min(data):
    data = remove_all(data,[None,""])
    if len(data) > 0: 
        if is_number(data[0]): return __builtin__.min(data)
        else: return None
    else: return None

# calculate the max of a given array of data
def max(data):
    data = remove_all(data,[None,""])
    if len(data) > 0: 
        if is_number(data[0]): return __builtin__.max(data)
        else: return None
    else: return None

# calculate the velocity of change of a given array of data
def velocity(in_x,in_y):
    x = []
    y = []
    # if data is invalid, remove it from both the x and y arrays
    for i in range(len(in_y)):
        if in_y[i] is not None and in_y[i] != "None" and is_number(in_y[i]):
            x.append(in_x[i])
            y.append(in_y[i])
    # at least two values needed
    if len(y) >= 2:
        # normalize the x data to be in the range [0,1]
        min = x[0]
        max = x[len(x)-1]
        for i in range(0,len(x)): x[i] = float(x[i]-min)/float(max-min)
        # apply linear regression to interpolate the data
        # TODO: numpy alternative
        #z = numpy.polyfit(x,y,1)
        # return the coefficient
        return normalize(z[0],"float_2")
    else: return None

# calculate the avg of a given array of data
def avg(data):
    data = remove_all(data,[None,""])
    if len(data) > 0:
        if is_number(data[0]): return normalize(tinynumpy.array(data).mean())
        else: return __builtin__.max(set(data), key=data.count)
    else: return None

# calculate the sum of a given array of data
def sum(data):
        data = remove_all(data,[None,""])
        if len(data) > 0:
                if is_number(data[0]): return normalize(tinynumpy.array(data).sum())
                else: return 0
        else: return 0

# count the items of a given array of data
def count(data):
    data = remove_all(data,[None,""])
    return len(data)

# count the (unique) items of a given array of data
def count_unique(data):
        data = remove_all(data,[None,""])
        return len(set(data))
        
# return a random int between min and max
def randint(min,max):
    return random.randint(min,max)
    
# convert a hex string into an integer
def hex2int(hex):
    try:
        hex = "0x"+hex.replace(" ","")
        return int(hex, 16)
    except: return None
