#import json
try:
    from collections import OrderedDict
except:
    from ordered_dict import OrderedDict
import os
import math

import numpy as np
import math
import jsonutil


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
    parsed = jsonutil.relaxed_loads(raw, object_pairs_hook=OrderedDict)
    return parsed

def dryrun(traj, filename="traj.trj"):
    """
    return the sequence of points visited by a trajectory.
    """

    never_write = []
    always_write = []
    points = []
    # Set the initial context to contain sprintf and math functions
    context = {"sprintf": lambda pattern,*args: pattern%args}
    context.update((k,v) for k,v in math.__dict__.items()
                   if not k.startswith('_')) 

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

    constants = context.copy()
    for k,v in traj.items():
        if str(k) in ("fileGroup", "fileName", "entryName", "filePrefix"):
            # delayed evaluation of filename handlers
            context["_"+k] = v
        elif str(k) in ("trajName", "descr", "neverWrite", "alwaysWrite"):
            # keywords evaluated in the current context
            context[k] = _eval(v, context)
        elif str(k) == "init":
            _init(v, context)
            constants = context.copy()
        elif str(k) == "loops":
            # Set volatiles here so they don't end up in constants.  The
            # variables in constants are not recorded in the dryrun table.

            # Pretend initial state of file counters
            context.update({
                'fileNum': 42,
                'instFileNum': 142,
                'expPointNum': 1042,
            })

            # Point number is set to zero at the start of each trajectory
            context['pointNum'] = 0

            points.extend(_loop(v,context))
        else:
            raise ValueError("unknown keyword %r"%k)

    return points, constants

class JSObject(object):
    def __repr__(self): return repr(self.__dict__)
    def __getitem__(self, k): return self.__dict__[k]

def _init(traj, context):
    for k,v in traj.items():
        if isinstance(v,OrderedDict):
            obj = JSObject()
            context[k] = obj
            for field_name, field_value in v.items():
                setattr(obj,field_name, _eval(field_value, context))
        else:
            context[k] = _eval(v, context)

def _eval(expr, context):
    """
    Evaluate an expression in a context.
    """
    if isinstance(expr, basestring):
        #import pprint; pprint.pprint(context)
        #print "eval",expr
        return eval(expr, {}, context)
    else:
        return expr

def _loop(traj, context):
    """
    Process the loops construct.
    """
    for section in traj:
        for p in _one_loop(section, context): yield p

def _one_loop(traj, context):
    """
    Process one of a series of loops in a loops construct.
    """
    loop_vars = []
    loop_len = 1
    for var,value in traj["vary"].items():
        if isinstance(value, OrderedDict):
            if "range" in value:
                loop_vars.append((var, _range(value["range"], context, loop_vars)))
            elif "list" in value:
                loop_vars.append((var, _list(value["list"], context, loop_vars)))
        elif isinstance(value, list):
            if len(loop_vars):
                points = [_eval(vi, ctx)
                          for vi,ctx in zip(value, _cycle_context(context,loop_vars))]
            else:
                points = [_eval(vi, context) for vi in value]
            loop_vars.append((var, points))
        else:
            if len(loop_vars):
                points = [_eval(value, ctx)
                          for ctx in _cycle_context(context,loop_vars)]
            else:
                points = [_eval(value, context)]
            loop_vars.append((var, points))
    for ctx in _cycle_context(context, loop_vars):
        if "loops" in traj:
            for pt in _loop(traj["loops"],ctx): 
                yield pt
                _update_global_context(context,ctx)
        else:
            _set_file(ctx)
            yield ctx  # ctx is a point
            _next_point(ctx)
            _update_global_context(context,ctx)

def _update_global_context(globals,locals):
    globals['pointNum'] = locals['pointNum']
    globals['fileNum'] = locals['fileNum']
    globals['instFileNum'] = locals['instFileNum']
    globals['expPointNum'] = locals['expPointNum']
    globals['_groups'] = locals['_groups']

def _next_point(ctx):
    ctx['pointNum'] += 1
    ctx['expPointNum'] += 1

def _set_file(ctx):
    group  = _eval(ctx['_fileGroup'], ctx)
    if group not in ctx['_groups']:
        ctx['_groups'].add(group)
        ctx['fileNum'] += 1
        ctx['instFileNum'] += 1
    ctx['fileGroup'] = group
    ctx['filePrefix'] = _eval(ctx['_filePrefix'], ctx)
    ctx['fileName'] = _eval(ctx['_fileName'], ctx)
    ctx['entryName'] = _eval(ctx['_entryName'], ctx)

def _cycle_context(context, loop_vars):
    """
    Yield a series of contexts with values for prior looping parameters.
    """
    names, values = zip(*loop_vars)
    for vi in zip(*values):
        ctx = context.copy()
        ctx.update(zip(names,vi))
        yield ctx

def _range(traj, context, loop_vars):
    """
    Process the range directive in loop:vary.

    Return the list of points generated by the range.
    """
    loop_len = len(loop_vars[0][1]) if len(loop_vars)>0 else 0

    if isinstance(traj, int):
        # range: n -> [0, 1, ..., n-1]
        points = np.arange(traj)
        #points = np.arange(traj+1)

    else:
        #print "_range"
        #print "traj",traj
        #print "ctx",context
        #print "vars",loop_vars
        trajcopy = traj.copy()
        start = _eval(trajcopy.pop("start",None), context)
        step = _eval(trajcopy.pop("step",None), context)
        stop = _eval(trajcopy.pop("stop",None), context)
        n = _eval(trajcopy.pop("n",None), context)
        center = _eval(trajcopy.pop("center",None), context)
        width = _eval(trajcopy.pop("width",None), context)
        if trajcopy:
            raise ValueError("unknown keys in range "+str(trajcopy))

        bits = 1*(start is not None) + 2*(stop is not None) + 4*(step is not None) + 8*(n is not None) + 16*(center is not None) + 32*(width is not None)
        n_or_len = n if n is not None else loop_len

        # There are twenty ways to pick three of start, step, stop, n, center, width
        # TODO: what about step < 0?
        if bits == 1+2+4: # start - stop - step
            points = np.arange(start,stop+1e-5*step,step)
        elif bits in (1+2+8,1+2): # start - stop - n
            points = np.linspace(start,stop,n_or_len)

        elif bits == (1+16+4): # start - center - step
            points = np.arange(start,2*center-start+1e-5*step,step)
        elif bits in (1+16+8,1+16): # start - center - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(start,2*center-start,n_or_len)
        elif bits == 1+32+4: # start - width - step
            points = np.arange(start,start+width+1e-5*step,step)
        elif bits in (1+32+8,1+32): # start - width - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(start,start+width,n_or_len)

        elif bits == (2+16+4): # stop - center - step
            points = np.arange(stop,2*center-stop-1e-5*step,-step)[::-1]
        elif bits in (2+16+8,2+16): # stop - center - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(2*center-stop,stop,n_or_len)
        elif bits == (2+32+4): # stop - width - step
            points = np.arange(stop,stop-width-1e-5*step,-step)[::-1]
        elif bits in (2+32+8,2+32): # stop - width - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(stop-width,stop,n_or_len)

        elif bits == (16+32+4): # center - width - step
            points = np.arange(center-width/2, center+width/2+1e-5*step, step)
        elif bits in (16+32+8,16+32): # center - width - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(center-width/2,center+width/2,n_or_len)

        elif bits in (1+4+8,1+4): # start - step - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(start,start+(n_or_len-1)*step,n_or_len)
        elif bits in (2+4+8,2+4): # stop - step - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(stop-(n_or_len-1)*step,stop,n_or_len)
        elif bits in (16+4+8,16+4): # center - step - n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            points = np.linspace(center-(n_or_len-1)*step/2.0, center+(n_or_len-1)*step/2.0, n_or_len)

        # width - step - n:  no anchor at start, stop or center
        # start - stop - width: no step size or number of steps
        # start - stop - center:  no step size or number of steps
        # start - center - width: no step size or number of steps
        # stop - center - width: no step size or number of steps

        elif bits in (8,0):  # n by itself means 0, 1, ..., n
            if n_or_len == 0: raise ValueError("unknown range length for "+str(traj))
            #points = np.arange(n+1 if n else loop_len)
            points = np.arange(n_or_len)
        else:
            raise ValueError("invalid parameter combination in range "+str(traj))

    if loop_len and len(points) != loop_len:
        raise ValueError("range different from number of points in loop for "+str(traj))
    return points

def _list(traj, context, loop_vars):
    """
    Process the list directive in loop:vary.

    Return the list of points generated by the list.
    """
    trajcopy = traj.copy()
    points = trajcopy.pop("value",[])
    cyclic = trajcopy.pop("cyclic",False)
    if trajcopy:
        raise ValueError("unknown keys in list "+str(trajcopy))
    if len(points) == 0:
        raise ValueError("list has no length "+str(traj))

    loop_len = len(loop_vars[0][1]) if len(loop_vars)>0 else len(points)
    if loop_len == 0:
        # No previous looping variables yet, so no cycle context for points
        points = [_eval(pt, context) for pt in points]
    elif cyclic:
        n = len(points)
        points = [_eval(points[i%n], ctx)
                  for i,ctx in enumerate(_cycle_context(context, loop_vars))]
    else:
        n = len(points)-1
        points = [_eval(points[min(i,n)], ctx)
                  for i,ctx in enumerate(_cycle_context(context, loop_vars))]
    return points


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

def print_table(points, constants):
    columns = columnate(points, constants)
    keys, values = zip(*sorted(columns.items()))
    hw = [len(k) for k in keys]
    vw = [max(len(_csv_field(ri)) for ri in c) for c in values]
    w = [max(pair) for pair in zip(hw,vw)]
    print " ".join("%*s"%(wi,ki) for wi,ki in zip(w,keys))
    for line in zip(*values):
        print " ".join("%*s"%(wi,_csv_field(ci)) for wi,ci in zip (w,line))

POLSPEC_EXAMPLE = """
{
        "neverWrite": ["i"],
        "alwaysWrite": ["t1"],
        "entryName": "['A','B','C','D'][polarizationIn+2*polarizationOut]",
        "init": {
                "down": 0,
                "up": 1,
                "counter": {
                        "countAgainst": "'MONITOR'",
                        "monitorPreset": 30000
                },
                "vertSlitAperture1": 0.2,
                "vertSlitAperture2": 0.2
        },
        "loops": [{
                "vary": {
                        "detectorAngle": {
                                "range": {
                                        "start": 0,"stop": 4,"step": 0.02}
                        },
                        "sampleAngle": "detectorAngle/2.0",
                        "slit1Aperture": [1,2,3,4,5],
                        "slit2Aperture": {
                                "list": {
                                        "value": [1,2,3,1],
                                        "cyclic": true
                                }
                        }
                },
                "loops": [{
                        "vary": {
                                "i": {"range": 12},
                                "t0": "i*12+200",
                                "skip": "(t0==248)"
                        },
                        "loops": [{
                                "vary": {
                                        "polarizationIn": ["down","up","down","up"],
                                        "polarizationOut": ["down","down","up","up"]
                                }
                        }]
                }]
        }]
}
"""

SANS_EXAMPLE = """
{
  fileGroup: "pointNum",

  init: {

    "counter.countAgainst": "'TIME'",
    sample: {
      mode: "'Chamber'",
      aperture: 12.7,
      sampleThickness: 1
    },


    CONFIGS: { // helper map

      "1.5m6": { attenuator: 0, wavelength: 6, wavelengthSpread: 0.132, nguide: 2, guide:{aperture: 50.8}, beamstop: 4, beamStopX: 0.5, beamStopY: -0.3, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 150, detectorOffset: 25 },
      "1.5m6t": { attenuator: 9, wavelength: 6, wavelengthSpread: 0.132, nguide: 2, guide:{aperture: 50.8}, beamstop: 4, beamStopX: -15, beamStopY: -0.3, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 150, detectorOffset: 25 },
      "5m6": { attenuator: 0, wavelength: 6, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: 0.6, beamStopY: -0.4, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 },
      "5m6t": { attenuator: 6, wavelength: 6, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: -15, beamStopY: -0.4, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 },
      "5m20": { attenuator: 0, wavelength: 20, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: 0.2, beamStopY: -0.1, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 },
      "5m20t": { attenuator: 1, wavelength: 20, wavelengthSpread: 0.132, nguide: 0, guide:{aperture: 13.0}, beamstop: 2, beamStopX: 0.2, beamStopY: -0.1, beamStop: {beamCenterX: 64, beamCenterY: 64}, detectorPosition: 525, detectorOffset: 0 }
    },

    SAMPLE_NAMES: ["empty cell", "blocked beam", "sample1", "sample2", "sample3", "sample4", "sample5", "sample6", "sample7", "sample8"],

    COUNT_TIMES: {
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
    },

    CONFIGURATION_ORDER: ["1.5m6", "5m6", "5m6t", "5m20t", "5m20"],

    SAMPLE_INTENTS: {
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
    }
  },
  loops: [{ // temp loop
    vary: { T: {range: 6},
      sampleTemperature: "15.0 + T*5.0"
    },
    loops: [{ // config loop
      vary: {
        CTR: {range: 5},
        // this will work if a mapping device called
        // "deviceConfig"
        // is in the device model
        deviceConfig: "CONFIGS[CONFIGURATION_ORDER[CTR]]"
      },
      loops: [{ // sample loop
        vary: {
          S: {range: 10},
          SNAME: "SAMPLE_NAMES[S]",
          sample: {index: "S" },
          INTENT: "SAMPLE_INTENTS[SNAME]",
          COUNTER_VALUE : "COUNT_TIMES[SNAME][CONFIGURATION_ORDER[CTR]]",
          counter: {timePreset: "COUNTER_VALUE"},
          skip : "COUNTER_VALUE == 0" // skip the point
        },
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

if __name__ == "__main__":
    main()
