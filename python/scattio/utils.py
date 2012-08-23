"""
Utility functions
"""
import os
import time
import datetime
import struct

def field_label(name,units):
    """
    Create a label like 'A3 setpoint (degrees)'
    """
    #print "label a,b",a,b
    try:
        a,b = name.split('.')
    except:
        a,b = name,''
    if a: a = " ".join(a.split("_")).capitalize()
    if b: b = " ".join(a.split("_"))
    #print "now",a,b
    if units:
        return ' '.join(v for v in (a,b,'(%s)'%units) if v)
    else:
        return ' '.join(v for v in (a,b) if v)

def data_as(path, units):
    from . import unit
    return unit.Converter(path.attrs["units"]).__call__(path.value, units)

def template(filename):
    path = os.path.join(os.path.dirname(__file__),filename)
    return path

def example(*args):
    return os.path.join(os.path.dirname(__file__),"examples",*args)

def format_timestamp(t):
    """
    Construct a utc offset timestamp containing the local time.
    """
    if isinstance(t, datetime.datetime):
        t = t.timetuple()
    dt = (time.timezone,time.altzone)[t.tm_isdst]
    local = time.strftime('%Y-%m-%dT%H:%M:%S',t)
    sign = "+" if dt >= 0 else "-"
    offset = "%02d:%02d"%(abs(dt)//3600,(abs(dt)%3600)//60)
    return local+sign+offset

# From: www.mpp.mpg.de/~huber/VMSSIG/src/C/lib_routines/VAX-IEEE-FLOAT.C
# X-VMS-News: vax3 comp.os.vms:1034
# From: woods@ncar.ucar.edu (Greg Woods)
# Subject:Re: difference between vax floating point representation and IEEE
# Date: 21 Jul 88 22:08:44 GMT
# Message-ID:<462@ncar.ucar.edu>
#  
# In article <2256@hubcap.UUCP> ghosh@hubcap.UUCP (Amitava Ghosh) writes:
# >does anyone know what the difference is between the IEEE floating
# >point representation and the way the VAX stores numbers. If so
# >how does one convert from one format to the other.
#  
#   Here's some C subroutines to convert back and forth between VAX and
# IEEE format. I use them to convert binary files between VAXes and Suns
# and it works fairly well. They all take a pointer to the data and
# how many data elements to convert as arguments.
# --Greg
def R4_VAX2IEEE(vax):
    """
    Convert 4 character VAX REAL*4 string into floating point
    """
    if ord(vax[1]) == 0:
        ieeeasstring = "".join((vax[2],vax[3],vax[0],vax[1]))
    else:
        ieeeasstring = "".join((vax[2],vax[3],vax[0],chr(ord(vax[1])-1)))
    return struct.unpack('<f',ieeeasstring)[0]

def R4_IEEE2VAX(value):
    """
    Convert 4 byte floating point to VAR REAL*4 string
    """
    ieee = struct.pack('<f', value)
    if all(c=='\0' for c in ieee):
        return "\0\0\0\0"
    else:
        return "".join((ieee[2], chr(ord(ieee[3])+1),ieee[0],ieee[1]))
