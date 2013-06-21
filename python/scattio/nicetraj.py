#!/usr/bin/env python
from __future__ import division

import os
import math
import random
import itertools

import numpy as np
import math
import jsonutil
import demjson
#from demjson import OrderedDict

try:
    raise ImportError("suppress PyV8")
    import PyV8
    class JSObject(object):
        def __repr__(self): return repr(self.__dict__)
        def __getitem__(self, k): return self.__dict__[k]
        def __setitem__(self, k, v): self.__dict__[k] = v
    class Context(PyV8.JSContext):
        def __getitem__(self, *args, **kw):
            return self.locals.__getitem__(*args, **kw)
        
        def __setitem__(self, *args, **kw):
            return self.locals.__setitem__(*args, **kw)

        def __delitem__(self, *args, **kw):
            return self.locals.__delitem__(*args, **kw)
            
        def __init__(self, **kw):
            super(PyV8.JSContext,self).__init__()
            self.enter()
            for k,v in kw.items(): self.locals[k] = v
            mathfn = ('abs','acos','asin','atan','atan2','ceil','cos','exp','floor','log',
                  'max','min','pow','random','round','sin','sqrt','tan')
            self.rhs("var "+",".join("%s=Math.%s"%(fn,fn) for fn in mathfn))
            self.rhs("var pi=Math.PI")
            add_sprintfJS(self)

        def get(self, name, default):
            return self.locals[name] if name in self.locals else default
            
        def update(self, update_dict, **kw):
            for k,v in update_dict.items(): self.locals[k] = v
            for k,v in kw.items(): self.locals[k] = v
                
        def items(self):
            return [(k,self.locals[k]) for k in self.locals.keys()]
            
        def state(self):
            return dict((k,self.locals[k]) for k in self.locals.keys())
            
        def assign(self, name, value):
            if '.' in name:
                deviceID, nodeID = name.split('.',1)
                obj = {}
                existing = self.get(deviceID, None)
                if isinstance(existing, dict): 
                    obj.update(existing)
                elif isinstance(existing, PyV8.JSObject):
                    obj.update((k,existing[k]) for k in existing.keys())
                obj[nodeID] = value
                self[deviceID] = obj
                #print "assigning",name,value,"as",deviceID,obj
            else:
                self[name] = value
        def rhs(self, expr):
            """
            Evaluate an expression in a context.
            """
            if isinstance(expr, basestring):
                #import pprint; pprint.pprint(self.__dict__)
                #print "eval",expr
                try:
                    return self.eval(expr)
                except Exception,exc:
                    raise exc.__class__, str(exc) + " when evaluating " + expr
            else:
                return expr
            
except ImportError:
    class JSObject(object):
        def __repr__(self): return repr(self.__dict__)
        def __getitem__(self, k): return self.__dict__[k]
        def __setitem__(self, k, v): self.__dict__[k] = v

    class Context(object):
        def __init__(self, **kw):
            self.__dict__ = kw.copy()
            # Set the initial context to contain sprintf and math functions
            self.assign("sprintf", lambda pattern,*args: pattern%args)
            self.update((k,v) for k,v in math.__dict__.items()
                        if not k.startswith('_'))
            self['random'] = random.random
        def __setitem__(self, k, v): self.__dict__[k] = v
        def __getitem__(self, k): return self.__dict__[k]
        def get(self, *args): return self.__dict__.get(*args)
        def update(self, *args, **kw): return self.__dict__.update(*args, **kw)
        def items(self): return self.__dict__.items()
        def state(self): 
            """
            Returns the current state of the context as a set of key-value pairs.

            Note that any variables which are references within the current state
            are not copied, and so may change as new expressions are evaluated
            within the context.
            """
            return self.__dict__.copy()
        def assign(self, name, value):
            """
            Assign a value to a name in the context.  If name is dotted, then assign 
            to a field of an object, copying the existing object beforehand or creating 
            a new one if it does not already exist.  The copy-on-write semantics
            allows us to more easily copy the existing context for later return.
            """
            if '.' in name:
                deviceID, nodeID = name.split('.',1)
                obj = JSObject()
                existing = self.get(deviceID, None)
                if isinstance(existing, JSObject): 
                    obj.__dict__.update(existing.__dict__)
                obj[nodeID] = value
                self.__dict__[deviceID] = obj
                #print "assigning",name,value,"as",deviceID,obj
            else:
                self.__dict__[name] = value
        def rhs(self, expr):
            """
            Evaluate an expression in a context.
            """
            if isinstance(expr, basestring):
                #import pprint; pprint.pprint(self.__dict__)
                #print "eval",expr
                try:
                    return eval(expr, {}, self.__dict__)
                except Exception,exc:
                    print self.__dict__
                    raise exc.__class__, str(exc) + " when evaluating " + expr
            else:
                return expr

def add_sprintfJS(context):
    with open(os.path.join(os.path.dirname(__file__),'sprintf.js')) as fid:
        source = fid.read()
    context.eval('exports={}')
    context.eval(source)
    context.eval('sprintf=exports.sprintf')
    del context['exports']

def load(filename):
    """
    Load a NICE trajectory from a file.
    """
    with open(filename,"rt") as fid:
        raw = fid.read()
    return parse(raw)

def parse(raw):
    """
    Parse a NICE trajectory from a string.
    """
    #parsed = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(raw)
    #parsed = jsonutil.relaxed_loads(raw, ordered=True)
    #parsed = demjson.decode(raw, allow_ordered_dict=True)
    parsed = demjson.decode(raw)
    parsed = tostr(parsed)
    return parsed

def tostr(tree):
    """ make unicode to string """
    if hasattr(tree, 'items'):
        #return OrderedDict((str(k),tostr(v)) for k,v in tree.items())
        return dict((str(k),tostr(v)) for k,v in tree.items())
    elif isinstance(tree, list):
        return [tostr(v) for v in tree]
    elif isinstance(tree, basestring):
        return str(tree)
    elif isinstance(tree, np.float64) and int(tree) == tree:
        return int(tree)
    else:
        return tree

def dryrun(traj, filename="traj.trj"):
    """
    return the sequence of points visited by a trajectory.
    """

    context = Context()

    # Defaults for keywords
    context.update({
        'trajName': os.path.splitext(os.path.basename(filename))[0],
        'descr': '',
        'alwaysWrite': [],
        'neverWrite': [],
        # Patterns for filenames.  These are evaluated for each point 
        # in the order below.
        '_fileGroup': "''",
        '_filePrefix': "trajName",
        '_fileName': "sprintf('%s%d',filePrefix,fileNum)",
        '_entryName': "''",
        # Observed groups. This will be extended each time a new
        # fileGroup is encountered, including the empty string, and
        # file number will be incremented as well.
        '_groups': set()
    })

    traj = traj.copy()
    # process init
    _init(traj.pop('init',{}), context)

    # remove loops and process the remaining top level keywords
    loops = traj.pop('loops',[])
    for k,v in traj.items():
        if str(k) in ("fileGroup", "fileName", "entryName", "filePrefix"):
            # delayed evaluation of filename handlers
            context["_"+k] = v
        elif str(k) in ("trajName", "descr", "neverWrite", "alwaysWrite"):
            # keywords evaluated in the current context
            context[k] = context.rhs(v)
        else:
            raise ValueError("unknown keyword %r"%k)

    # process loops last
    constants = context.state()

    # Pretend initial state of file counters.  Define them after constants
    # so that they will show up as columns in the dry run table.  In a
    # real trajectory, these would be set by the server
    context.update({
               'fileNum': 42,
                'instFileNum': 142,
                'expPointNum': 1042,
            })

    # Point number is set to zero at the start of each trajectory
    context.assign('pointNum', 0)

    # run the loops
    points = list(_loops(loops,context))

    return points, constants

def _init(traj, context):
    for name,v in traj:
        if hasattr(v,'items'):
            value = JSObject()
            for field_name, field_value in v.items():
                #print "evaluating",field_name,v
                setattr(value,field_name, context.rhs(field_value))
        else:
            #print "evaluating",v
            value = context.rhs(v)
        context.assign(name, value)

def _loops(traj, context):
    """
    Process the loops construct.
    """
    #print "_loops"
    for section in traj:
        for p in _one_loop(section, context): yield p
    #print "end loop"

def _one_loop(traj, context):
    """
    Process one of a series of loops in a loops construct.
    """
    #print "_one_loop"
    extra_keys = set(traj.keys()) - set(('vary','loops'))
    if extra_keys:
        raise ValueError("loop contains extra keys %s"%", ".join(sorted(extra_keys)))

    loop_vars = []
    for var,value in traj["vary"]:
        if hasattr(value, 'items'):
            if "range" in value:
                loop_vars.append((var, _range(value["range"], context, logsteps=False)))
            elif "logrange" in value:
                loop_vars.append((var, _range(value["logrange"], context, logsteps=True)))
            elif "list" in value:
                loop_vars.append((var, _list(value["list"], context, cycle=(loop_vars!=[]))))
        elif isinstance(value, list):
            # lists are implicit noncyclic lists with final repeated
            loop_vars.append((var, _list({'value': value}, context, cycle=(loop_vars!=[]))))
        else:
            # lists are implicit noncyclic lists of length 1 with final repeated
            loop_vars.append((var, _list({'value': [value]}, context, cycle=(loop_vars!=[]))))

    # Cycle through the loop variables
    # Since _cycle_context updates the context in place, there is no reason to look at
    # the _cycle_context yield value.  The _loops yield value, on the other hand, has
    # a copy of the context, and therefore needs to be forwarded to the caller.
    #print "cycling context"
    for _ in _cycle_context(context, loop_vars):
        if "loops" in traj:
            for pt in _loops(traj["loops"],context): yield pt
        else:
            _set_file(context)
            _next_point(context)
            yield context.state()  # ctx is a point
    #print "end oneloop"

def _next_point(context):
    context['pointNum'] += 1
    context['expPointNum'] += 1

def _set_file(context):
    group  = context.rhs(context['_fileGroup'])
    if group not in context['_groups']:
        context['_groups'].add(group)
        context['fileNum'] += 1
        context['instFileNum'] += 1
    context['fileGroup'] = group
    context['filePrefix'] = context.rhs(context['_filePrefix'])
    context['fileName'] = context.rhs(context['_fileName'])
    context['entryName'] = context.rhs(context['_entryName'])

def _cycle_context(context, loop_vars):
    """
    Yield a series of contexts with values for prior looping parameters.
    """
    while True:
        # Cycle through all the variables, updating the value.  If the
        # first variable completes its cycle, then signal an error.  If
        # subsequent values do not complete their cycles, then ignore
        # the additional values => no error checking on range sizes.
        first = True
        for name,cycle in loop_vars:
            #print "evaluating",name
            try: 
                value = cycle.next()
            except StopIteration: 
                if first: return
                else: raise ValueError("loop ended early for %r"%name)
            first = False
            context.assign(name, value)
        #print "yielding context",context
        yield context

def _logrange(start, stop, step):
    if start < stop and step > 1:
        L = []
        while start <= stop*1.0000001:
            L.append(start)
            start *= step
        return np.array(L)
    elif start > stop and step < 1:
        L = []
        while start >= stop*0.9999999:
            L.append(start)
            start *= step
        return np.array(L)
    else:
        return np.array([], dtype='double')

def _delta_steps(traj, start, stop, step, logsteps, reverse=False):
    step = abs(step)
    if step == 0:
       raise ValueError("step cannot be zero for "+str(traj))
    if logsteps and start <= 0:
        raise ValueError("log range must be positive for "+str(traj))
    if logsteps and step == 1:
        raise ValueError("log range must have step different from 1 for "+str(traj))
    if logsteps and step < 1:
        step = 1./step
    #print "delta",start,stop,step,reverse
    if reverse:
        if logsteps:
            if start > stop: step = 1/step
            points = _logrange(stop, start, 1/step)[::-1]
        else:
            if start > stop:  step = -step
            points = np.arange(stop, start-1e-5*step, -step)[::-1]
    else:
        if logsteps:
            if start > stop: step = 1/step
            points = _logrange(start, stop, step)
        else:
            if start > stop:  step = -step
            points = np.arange(start, stop+1e-5*step, step)
    if np.all(points == np.floor(points)):
        points = np.asarray(points, 'int')
    return points

def _n_steps(traj, start, stop, n, logsteps):
    if n == 0: 
        raise ValueError("unknown range length for "+str(traj))
    if logsteps and (start<=0 or stop<=0):
        raise ValueError("log range must be positive for "+str(traj))
    if logsteps:
        points = np.logspace(np.log10(start), np.log10(stop), n)
    else:
        points = np.linspace(start, stop, n)
    if np.all(points == np.floor(points)):
        points = np.asarray(points, 'int')
    return points

def _range(traj, context, logsteps):
    """
    Process the range directive in loop:vary.

    Return the list of points generated by the range.
    """
    if isinstance(traj, int):
        n = traj
        start = step = stop = center = width = None
    else:
        #print "_range"
        #print "traj",traj
        #print "context",context
        trajcopy = traj.copy()
        start = context.rhs(trajcopy.pop("start",None))
        step = context.rhs(trajcopy.pop("step",None))
        stop = context.rhs(trajcopy.pop("stop",None))
        n = context.rhs(trajcopy.pop("n",None))
        center = context.rhs(trajcopy.pop("center",None))
        width = context.rhs(trajcopy.pop("width",None))
        if trajcopy:
            raise ValueError("unknown keys in range "+str(trajcopy))


    bits = 1*(start is not None) + 2*(stop is not None) + 4*(step is not None) + 8*(n is not None) + 16*(center is not None) + 32*(width is not None)
    #print "bits",bits

    # There are twenty ways to pick three of start, step, stop, n, center, width
    # Convert these to start, stop, step/n, reverse
    reverse = False
    if bits in (1+2+4, 1+2+8): # start - stop - step/n
        pass # start, stop, step unchanged

    elif bits in (1+16+4, 1+16+8): # start - center - step/n
        stop = 2*center - start
    elif bits in (1+32+4, 1+32+8): # start - width - step/n
        stop = start + width

    elif bits in (2+16+4, 2+16+8): # stop - center - step/n
        start = 2*center - stop
        reverse = True
    elif bits in (2+32+4, 2+32+8): # stop - width - step/n
        start = stop - width
        reverse = True

    elif bits in (16+32+4, 16+32+8): # center - width - step/n
        start,stop = center - width/2., center + width/2.

    elif bits == 1+4+8: # start - step - n
        stop = start + (n-1)*abs(step)
        step = None # use linspace rather than arange

    elif bits == 2+4+8: # stop - step - n
        start = stop - (n-1)*abs(step)
        step = None # use linspace rather than arange

    elif bits == 16+4+8: # center - step - n
        start, stop = center - (n-1)*abs(step)/2., center + (n-1)*abs(step)/2.
        step = None # use linspace rather than arange

    # width - step - n:  no anchor at start, stop or center
    # start - stop - width: no step size or number of steps
    # start - stop - center:  no step size or number of steps
    # start - center - width: no step size or number of steps
    # stop - center - width: no step size or number of steps

    elif bits == 8:  # n by itself means 0, 1, ..., n-1
        if logsteps:
            start, stop = 1, 10**(n-1)
        else:
            start, stop = 0, n-1

    else:
        raise ValueError("invalid parameter combination in range "+str(traj))

    
    #print start, stop, step, n, logsteps, reverse
    if step is not None:
        points = _delta_steps(traj, start, stop, step, logsteps, reverse)
    else:
        points = _n_steps(traj, start, stop, n, logsteps)

    return iter(points)

def _list(traj, context, cycle=True):
    """
    Process the list directive in loop:vary.

    Return the list of points generated by the list.

    *cycle* should be false for the first loop variable, or the loop will go on
    forever.
    """
    trajcopy = traj.copy()
    points = trajcopy.pop("value",[])
    cyclic = trajcopy.pop("cyclic",False)
    if trajcopy:
        raise ValueError("unknown keys in list "+str(trajcopy))
    if len(points) == 0:
        raise ValueError("list has no length "+str(traj))

    if not cycle:
        return (context.rhs(p) for  p in points)
    elif cyclic:
        return (context.rhs(p) for p in itertools.cycle(points))
    else:
        return (context.rhs(p) for p in itertools.chain(iter(points),itertools.repeat(points[-1])))


def columnate(points, constants):
    """
    Convert a ragged point list [{k:value}] into regular columns {k:[value]}, with
    missing values replaced by None.
    """
    if len(points) == 0: raise ValueError("No points to columnate")
    columns = {}
    for i,pt in enumerate(points):
        ptkeys = set()
        for field,value in pt.items():
            if isinstance(value, JSObject):
                for subfield,subvalue in value.__dict__.items():
                    name = ".".join((field,subfield))
                    ptkeys.add(name)
                    if name in columns:
                        columns[name].append(subvalue)
                    else:
                        columns[name] = [None]*i + [subvalue]
            elif field in columns:
                columns[field].append(value)
                ptkeys.add(field)
            else:
                columns[field] = [None]*i + [value]
                ptkeys.add(field)
        for field in set(columns.keys())-ptkeys:
            columns[field].append(None)
    #print columns.keys()
    columns = dict((k,v) for k,v in columns.items()
                   if k.split('.')[0] not in constants)
    return columns

def _csv_field(v):
    """
    Format a value for output to a comma separated value file.
    """
    if v is None:
        return ''
    elif isinstance(v,basestring):
        return '"%s"'%v
    elif isinstance(v,int):
        return '%d'%v
    elif isinstance(v,float):
        return '%g'%v
    elif hasattr(v, 'items'):
        return "{"+", ".join("%s:%s"%(ki,_csv_field(vi)) for ki,vi in v.items())+"}"
    else:
        return '"%s"'%str(v)

def print_csv(points):
    """
    Print a set of points to a CSV table.
    """
    #print points[0]
    columns = columnate(points, constants)
    keys, values = zip(*sorted(columns.items()))
    print ",".join('"%s"'%k for k in keys)
    for line in zip(*values):
        print ",".join(_csv_field(v) for v in line)

def _header(name, width):
    n = len(name)
    if width > n+6:
        extra = width - (n+2)
        return " ".join(( "_"*(extra//2), name, "_"*((extra+1)//2) ))
    else:
        extra = width - n
        return "".join(( " "*(extra//2), name, " "*((extra+1)//2) ))

def print_table(points, constants):
    columns = columnate(points, constants)
    keys, values = zip(*sorted(columns.items()))
    hw = [len(k) for k in keys]
    vw = [max(len(_csv_field(ri)) for ri in c) for c in values]
    w = [max(pair) for pair in zip(hw,vw)]
    print " ".join(_header(ki,wi) for wi,ki in zip(w,keys))
    for line in zip(*values):
        print " ".join("%*s"%(wi,_csv_field(ci)) for wi,ci in zip (w,line))

POLSPEC_EXAMPLE = """
{
        "neverWrite": ["i","up","down","POLXS"],
        "alwaysWrite": ["t1"],
        // Polarization cross section is a 2 bit integer index into
        // the POLXS array, with one bit for the polarization in and
        // the other for the polarization out. 00: A, 01: B, 10: C, 11: D
        "entryName": "POLXS[polarizationIn + 2*polarizationOut]",
        "init": [
                ["POLXS", ["A", "B", "C", "D"]],
                ["down", 0],
                ["up", 1],
                ["counter", {
                        "countAgainst": "'MONITOR'",
                        "monitorPreset": 30000
                }],
                ["vertSlitAperture1", 0.2],
                ["vertSlitAperture2", 0.2]
        ],
        "loops": [{
                "vary": [
                        ["detectorAngle.softPosition", {
                                "range": {
                                        "start": 0,"stop": 2,"step": 0.2}
                        }],
                        ["sampleAngle", "detectorAngle.softPosition/2.0"],
                        ["slit1Aperture", [1,2,3,4,5]],
                        ["slit2Aperture", {
                                "list": {
                                        "value": [1,2,3],
                                        "cyclic": true
                                }
                        }]
                ],
                "loops": [{
                        "vary": [
                                ["i", {"range": 12}],
                                ["t0", "i*12+200"],
                                ["skip", "(t0==248)"]
                        ],
                        "loops": [{
                                "vary": [
                                        ["polarizationIn", ["down","up","down","up"]],
                                        ["polarizationOut", ["down","down","up","up"]]
                                ]
                        }]
                }]
        }]
}
"""

SANS_EXAMPLE = """
{
  fileGroup: "pointNum",

  init: [

    ["counter.countAgainst", "'TIME'"],
    ["sample", {
      mode: "'Chamber'",
      aperture: 12.7,
      sampleThickness: 1
    }],


    ["CONFIGS", { // helper map

      "1.5m6": { attenuator: 0, wavelength: 6, wavelengthSpread: 0.132, nguide: 2, guide:{aperture: 50.8}, beamstop: 4, beamStopX: 0.5, beamStopY: -0.3, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 150, detectorOffset: 25 },
      "1.5m6t": { attenuator: 9, wavelength: 6, wavelengthSpread: 0.132, nguide: 2, guide:{aperture: 50.8}, beamstop: 4, beamStopX: -15, beamStopY: -0.3, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 150, detectorOffset: 25 },
      "5m6": { attenuator: 0, wavelength: 6, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: 0.6, beamStopY: -0.4, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 },
      "5m6t": { attenuator: 6, wavelength: 6, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: -15, beamStopY: -0.4, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 },
      "5m20": { attenuator: 0, wavelength: 20, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: 0.2, beamStopY: -0.1, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 },
      "5m20t": { attenuator: 1, wavelength: 20, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: 0.2, beamStopY: -0.1, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 }
    }],

    ["SAMPLE_NAMES", ["empty cell", "blocked beam", "sample1", "sample2", "sample3", "sample4", "sample5", "sample6", "sample7", "sample8"]],

    ["COUNT_TIMES", {
      "empty cell":     {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      "blocked beam": {"1.5m6":300, "5m6":900, "5m6t":0, "5m20":1800, "5m20t":0},
      sample1:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      sample2:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      sample3:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      sample4:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      sample5:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      sample6:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      sample7:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180},
      sample8:  {"1.5m6":300, "5m6":900, "5m6t":180, "5m20":1800, "5m20t":180}
    }],

    ["CONFIGURATION_ORDER", ["1.5m6", "5m6", "5m6t", "5m20t", "5m20"]],

    ["SAMPLE_INTENTS", {
      "empty cell": "'EmptyCell'",
      "blocked beam": "'BlockedBeam'",
      sample1: "'sample'",
      sample2: "'sample'",
      sample3: "'sample'",
      sample4: "'sample'",
      sample5: "'sample'",
      sample6: "'sample'",
      sample7: "'sample'",
      sample8: "'sample'"
    }]
  ],
  loops: [{ // temp loop
    vary: [ 
      ["T", {range: 6}],
      ["sampleTemperature", "15.0 + T*5.0"]
    ],
    loops: [{ // config loop
      vary: [
        ["CTR", {range: 5}],
        // this will work if a mapping device called
        // "deviceConfig"
        // is in the device model
        ["deviceConfig", "CONFIGS[CONFIGURATION_ORDER[CTR]]"]
      ],
      loops: [{ // sample loop
        vary: [
          ["S", {range: 10}],
          ["SNAME", "SAMPLE_NAMES[S]"],
          ["sample", {index: "S" }],
          ["INTENT", "SAMPLE_INTENTS[SNAME]"],
          ["COUNTER_VALUE",  "COUNT_TIMES[SNAME][CONFIGURATION_ORDER[CTR]]"],
          ["counter", {timePreset: "COUNTER_VALUE"}],
          ["skip", "COUNTER_VALUE == 0"] // skip the point
        ],
      }] // end of sample loop
    }]// end of guideConfigs loop
  }]// end of temperature loop
}
"""

def demo(traj, trajname):
    print_table(*dryrun(traj))


def main():
    """
    Perform dryrun on file from command line
    """
    import sys
    if len(sys.argv) != 2:
        print >>sys.stderr, "Expected trajectory file, refl or sans"
        sys.exit()

    if sys.argv[1] == "refl": demo(parse(POLSPEC_EXAMPLE), "polrefl.trj")
    elif sys.argv[1] == "sans": demo(parse(SANS_EXAMPLE), "sans.trj")
    else: demo(load(sys.argv[1]), sys.argv[1])

def test_ranges():
    context = Context()
    def _test_lin(r, expected):
       points = np.array(list(_range(r, context, False)))
       #print r, points, expected
       if np.linalg.norm(points - expected) > 1.e-10:
           print r, points, expected
    def _test_log(r, expected):
       points = np.array(list(_range(r, context, True))) 
       if np.linalg.norm(points - expected) > 1.e-10:
           print r, points, expected

    # check negative step
    _test_lin(dict(start=1,stop=5.5,step=-1),[1,2,3,4,5])

    # start - stop - n/step
    _test_lin(dict(start=1,stop=5.5,step=1),[1,2,3,4,5])
    _test_lin(dict(start=5,stop=1.5,step=1),[5,4,3,2])
    _test_lin(dict(start=1,stop=5,n=5),[1,2,3,4,5])
    _test_lin(dict(start=5,stop=2,n=4),[5,4,3,2])

    _test_log(dict(start=1,stop=1001,step=10),[1,10,100,1000])
    _test_log(dict(start=1000,stop=0.8,step=10),[1000,100,10,1])
    _test_log(dict(start=1,stop=1000,n=4),[1,10,100,1000])
    _test_log(dict(start=1000,stop=1,n=4),[1000,100,10,1])

    # start - center/width - n/step
    _test_lin(dict(start=5,center=7.1,step=1),[5,6,7,8,9])
    _test_lin(dict(start=5,width=4.1,step=1),[5,6,7,8,9])
    _test_lin(dict(start=5,center=7,n=5),[5,6,7,8,9])
    _test_lin(dict(start=5,width=4,n=5),[5,6,7,8,9])
    _test_lin(dict(start=5,center=2.9,step=1),[5,4,3,2,1])
    _test_lin(dict(start=5,width=-4.1,step=1),[5,4,3,2,1])
    _test_lin(dict(start=5,center=3,n=5),[5,4,3,2,1])
    _test_lin(dict(start=5,width=-4,n=5),[5,4,3,2,1])

    # stop - center/width - n/step
    _test_lin(dict(stop=5,center=7.1,step=1),[9,8,7,6,5])
    _test_lin(dict(stop=5,width=4.1,step=1),[1,2,3,4,5])
    _test_lin(dict(stop=5,center=7,n=5),[9,8,7,6,5])
    _test_lin(dict(stop=5,width=4,n=5),[1,2,3,4,5])
    _test_lin(dict(stop=5,center=2.9,step=1),[1,2,3,4,5])
    _test_lin(dict(stop=5,width=-4.1,step=1),[9,8,7,6,5])
    _test_lin(dict(stop=5,center=3,n=5),[1,2,3,4,5])
    _test_lin(dict(stop=5,width=-4,n=5),[9,8,7,6,5])


    # center - width - n/step
    _test_lin(dict(center=5,width=4,step=1),[3,4,5,6,7])
    _test_lin(dict(center=5.5,width=5,step=1),[3,4,5,6,7,8])
    _test_lin(dict(center=5,width=4,n=5),[3,4,5,6,7])
    _test_lin(dict(center=5.5,width=5,n=6),[3,4,5,6,7,8])

    # start/stop/center - step - n
    _test_lin(dict(start=5, step=1, n=4), [5,6,7,8])
    _test_lin(dict(stop=5, step=1, n=4), [2,3,4,5])
    _test_lin(dict(center=5.5, step=1, n=4), [4,5,6,7])
    _test_lin(dict(center=5, step=1, n=5), [3,4,5,6,7])

    # Bare n
    _test_lin(dict(n=5), [0,1,2,3,4])
    _test_log(dict(n=3), [1,10,100])
    _test_lin(5, [0,1,2,3,4])
    _test_log(3, [1,10,100])



if __name__ == "__main__":
    #test_ranges()
    main()
