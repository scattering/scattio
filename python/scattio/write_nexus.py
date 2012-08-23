"""
Internal helper module which converts a dataset to nexus.
"""

import re

import numpy

import h5nexus

from .utils import field_label

def main_driver(convert):
    import sys
    if len(sys.argv) < 2:
        print >>sys.stderr, "usage: %s [-o pattern] file..."
        sys.exit(1)
    if sys.argv[1] == '-o':
        outfile = sys.argv[2]
        infiles = sys.argv[3:]
    else:
        outfile = None
        infiles = sys.argv[1:]
    for infile in infiles:
        convert(infile, outfile)

def write_nexus(outfile, data, nexus_layout):
    outfile = _expand_pattern(outfile, data)
    #print "outfile",outfile
    
    # create filename from scanid
    creator = "ncnrconvert"
    path,entryname = outfile.split(':')
    if path:
        root = h5nexus.open(path+".nxs", mode="a", creator=creator)
    else:
        root = h5nexus.open(None, mode="mem", creator=creator)
    entry = h5nexus.group(root, entryname, 'NXentry')
    das = _make_daslogs(entry, data)
    _make_group(das, entry, nexus_layout, data)
    return root

def _expand_pattern(pattern, data):
    """
    substitute into scanid to create output file entry.
    
    Uses the same pattern format as the NICE trajectory  code.
    """
    parts = re.split(r'<(.*?)>', pattern)
    missing = [pi for i,pi in enumerate(parts)
               if i%2==1 and pi not in data]
    if missing:
        raise IOError("Filename pattern substitution for %r cannot resolve %s"
                      % (pattern,", ".join(missing)))
    subst = [(pi if i%2==0 else str(data[pi]['value'])) 
             for i,pi in enumerate(parts)]
    return "".join(subst)

def _make_daslogs(path, data):
    daslogs = h5nexus.group(path, "DASlogs", "NXcollection")
    for k,v in data.items():
        #print "make_daslogs",k
        groupname,fieldname = k.split('.')
        try:
            group = daslogs[groupname]
        except KeyError:
            group = h5nexus.group(daslogs, groupname, "NXcollection")
        
        _make_field(group, fieldname, v)
    return daslogs
        
def _make_group(das, path, config, data):
    #print "group",path,config
    for k,v in config.items():
        #print "config",k,v
        if "$NX" in k:
            # subgroup name(NXclass)
            name, nxclass = k.split('$')
            # Create the DAS entry for the sensor
            p = h5nexus.group(path, name, nxclass)
            _make_group(das, p, v, data)
        elif isinstance(v, dict):
            # numeric value and units
            _make_field(path, k, v)
        elif isinstance(v, list):
            # array of floats
            _make_field(path, k, {'value': numpy.asarray(v), 
                                  'units': ''})
        elif v.startswith('->'):
            # link to data column (turns into immediate value)
            source = v[2:].replace('.','/')
            target = "/".join((path.name,k))
            #print "linking",source,"->",target
            try:
                p = h5nexus.link(das[source], target)
            except KeyError:
                print KeyError("Could not link %r to %r"%(target,source))
                continue


        elif v.startswith('$'):
            # immediate value from data column
            key = v[1:]
            if key in data:
                _make_field(path, k, data[key])
            else:
                print "field %r not found in data"%key
                continue
        else:
            try:
                # Check for "value units"
                valuestr,units = v.split(' ')
                field = {'value': float(valuestr), 'units': units}
            except:
                try:
                    # Check for number
                    field = {'value': float(v), 'units': None}
                except:
                    # Otherwise string
                    field = {'value': v, 'type':'|S'}
            _make_field(path, k, field)

def _make_field(path, name, conf):
    dtype = conf.get('type',None)
    units = conf.get('units',None)
    label = conf.get('label',field_label(name,units))
    if 'value' not in conf:
        raise KeyError("missing value for %r at %r"%(name,path))
    value = conf['value']
    if dtype is None:
        try: 
            value[:0]+''
            dtype='|S'
        except:
            dtype='float32'
    
    #print "creating %r"%label,name,value,units,dtype
    if numpy.isscalar(value): value = [value]

    value = numpy.asarray(value,dtype=dtype)
    attrs = dict((k,v)
                 for k,v in conf.items()
                 if k not in ('type','units',
                              'long_name','value','fields'))
    h5nexus.field(path, name, data=value, units=units,
                label=label, attrs=attrs)


