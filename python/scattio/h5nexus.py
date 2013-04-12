"""
NeXus file interface.

Note that this changes h5py to include a natural naming interface with
g.Fname referencing field *name* in Group *g*, and g.Aname referencing
attribute *name* in the Group or Dataset *g*.  It also adds the tree()
method to groups, which returns a formatted summary tree.
"""
__all__ = ["open", "group", "field", "append", "extend", "link",
           "walk", "datasets"]
import new
import os

import h5py as h5
import numpy

# The following forces natural naming onto 
from . import h5natural
from . import iso8601

# Conforms to the following version of the NeXus standard
__version__ = "4.2.1"

# Version of the library
api_version = "0.1"

_MEMFILE_COUNT = 0

def open(filename, mode="r", timestamp=None, creator=None, **kw):
    """
    Open a NeXus file.

    *mode* : string
        File open mode.

        ==== =========================================
        Mode Behavior
        ---- -----------------------------------------
        r    open existing file read-only
        r+   open existing file read-write
        w    create empty file
        w-   create empty file, fail if exists
        a    open file read-write or create empty file
        mem  create empty in-memory file
        ==== =========================================

    *timestamp* : string, datetime, time_struct or float
        On file creation, records a timestamp for the file.  This can be
        a float returned by time.time(), a time_struct returned by
        time.localtime(time.time()), an ISO 8601 string or a datetime
        object such as that returned by datetime.datetime.now().
    *creator* : string
        On file creation, records the name of the program or facility that
        created the data.  If not specified, then the creator field will
        not be written.

    Additional keywords (*driver*, *libver*) are passed to the h5py File
    function.  This allows, for example, the creation of unbuffered
    files which write the data immediately when it arrives without the
    need to flush.  See the h5py documentation for details.

    In memory file objects could be created using driver="core" and
    backing_store=True|False.  However, even when backing_store is
    False, the filename must be unique within the process, so we instead
    provide the special open mode of "mem".  If a filename is provided,
    then the file is opened with the core driver and backing_store=True.
    When it is not provided a unique temporary filename is generated
    and backing_store=False.
        
    Returns an H5 file object.
    """
    if mode=="mem":
        mode = "a"
        if filename:
            kw.update({'driver':'core', 'backing_store':True})
        else:
            kw.update({'driver':'core', 'backing_store':False})
            global _MEMFILE_COUNT
            _MEMFILE_COUNT += 1
            filename = "temp%05d.nxs"%_MEMFILE_COUNT
            
    preexisting = os.path.exists(filename)
    
    f = h5.File(filename, mode, **kw)
    if (mode == "a" and not preexisting) or mode == "w":
        if timestamp is None:
            timestr = iso8601.now()
        else:
            # If given a time string, check that it is valid
            try:
                timestamp = iso8601.parse_date(timestamp)
            except TypeError:
                pass
            timestr = iso8601.format_date(timestamp)
        f.attrs['NX_class'] = 'NXroot'
        f.attrs['file_name'] = filename
        f.attrs['file_time'] = timestr
        # TODO: should use libver to keyword to set the version.
        f.attrs['HDF5_Version'] = h5.version.hdf5_version
        f.attrs['NeXus_version'] = __version__
        if creator is not None:
            f.attrs['creator'] = creator
    return f

def group(node, path, nxclass):
    """
    Create a NeXus group.

    *path* can be absolute or relative to the node.

    This function marks the group with its NeXus class name *nxclass*.
    Unlike the underlying H5py create_group method on node, the entire
    path up to the created group must exist.

    Returns an H5 group object.
    """
    node,child = _get_path(node,path)
    try:
        group = node.create_group(child)
    except Exception,exc:
        _annotate_exception(exc, "when creating group %r"%path)
        raise
    group.attrs['NX_class'] = nxclass.encode('UTF-8')
    return group

def link(node, link):
    """
    Create an internal link from an HDF-5 group or dataset to another
    dataset.

    *node* : h5 object
        Source of the link.
    *link* : string
        Path which should link to source.  This can be an absolute path,
        or it can be relative to the parent group of the node.

    A 'target' attribute is added to the source object indicating its
    path.  When processing the file later, you can locate the source
    of the link using::

        str(node.name) == node.attrs['target']

    The NeXus standard also supports external links using the standard
    HDF-5 external linking interface::

        h5file[link] = nexus.h5.ExternalLink(filename,path)
    """
    if not 'target' in node.attrs:
        node.attrs["target"] = str(node.name) # Force string, not unicode
    node.parent[link] = node

# Default chunk size for extensible objects
CHUNK_SIZE = 1000
# Options passed to h5 create_dataset
_CREATE_OPTS = ['chunks','maxshape','compression',
                'compression_opts','shuffle','fletcher32']
def field(node, path, **kw):
    """
    Create a data object.

    :Parameters:

    *node* : H5 object
        Handle to an H5 object.  This could be a file or a group.

    *path* : string
        Path to the data.  This could be a full path from the root
        of the file, or it can be relative to a group.  Path components
        are separated by '/'.

    *data* : array or string
        If the data is known in advance, then the value can be given on
        creation. Otherwise, use *shape* to give the initial storage
        size and *maxshape* to give the maximum size.

    *units* : string
        Units to display with data.  Required for numeric data.

    *label* : string
        Axis label if data is numeric.  Default for field dataset_name
        is "Dataset name (units)".

    *attrs* : dict
        Additional attributes to be added to the dataset.


    :Storage options:

    *dtype* : numpy.dtype
        Specify the storage type for the data.  The set of datatypes is
        limited only by the HDF-5 format, and its h5py interface.  Usually
        it will be 'int32' or 'float32', though others are possible.
        Data will default to *data.dtype* if *data* is specified, otherwise
        it will default to 'float32'.

    *shape* : [int, ...]
        Specify the initial shape of the storage and fill it with zeros.
        Defaults to [1, ...], or to the shape of the data if *data* is
        specified.

    *maxshape* : [int, ...]
        Maximum size for each dimension in the dataset.  If any dimension
        is None, then the dataset is resizable in that dimension.
        For a 2-D detector of size (Nx,Ny) with Nt time of flight channels
        use *maxshape=[Nx,Ny,Nt]*.  If the data is to be a series of
        measurements, then add an additional empty dimension at the front,
        giving *maxshape=[None,Nx,Ny,Nt]*.  If *maxshape* is not provided,
        then use *shape*.

    *chunks* : [int, ...]
        Storage block size on disk, which is also the basic compression
        size.  By default *chunks* is set from maxshape, with the
        first unspecified dimension set such that the chunk size is
        greater than nexus.CHUNK_SIZE. :func:`make_chunks` is used
        to determine the default value.

    *compression* : 'none|gzip|szip|lzf' or int
        Dataset compression style.  If not specified, then compression
        defaults to 'szip' for large datasets, otherwise it defaults to
        'none'. Datasets are considered large if each frame in maxshape
        is bigger than CHUNK_SIZE.  Eventmode data, with its small frame
        size but large number of frames, will need to set compression
        explicitly.  If compression is an integer, then use gzip compression
        with that compression level.

    *compression_opts* : ('ec|nn', int)
        szip compression options.

    *shuffle* : boolean
        Reorder the bytes before applying 'gzip' or 'hzf' compression.

    *fletcher32* : boolean
        Enable error detection of the dataset.

    :Returns:

    *dataset* : h5 object
        Reference to the created dataset.
    """
    node,child = _get_path(node,path)

    # Set the default field creation opts
    create_opts = {}
    for k in _CREATE_OPTS:
        v = kw.pop(k,None)
        if v is not None: create_opts[k] = v

    data = kw.pop('data', None)
    dtype = kw.pop('dtype', None)
    shape = kw.pop('shape', None)
    units = kw.pop('units', None)
    label = kw.pop('label', None)
    attrs = kw.pop('attrs', {})

    # Fill in default creation options
    if data is not None:
        # Creating a field with existing data
        # Note that NeXus doesn't support scalar field values.
        try: data = data.encode('UTF-8')
        except AttributeError: pass
        if numpy.isscalar(data): data = [data]
        #print node, path, dtype
        if dtype is None:
            data = numpy.asarray(data)
        else:
            data = numpy.asarray(data, dtype=dtype)
        if ('compression' not in create_opts
            and data.nbytes > CHUNK_SIZE):
            create_opts['compression'] = 9
        create_opts['data'] = data
        dtype = data.dtype
    else:
        # Creating a field to be filled in later
        maxshape = create_opts.pop('maxshape', None)
        chunks = create_opts.pop('chunks', None)
        compression = create_opts.pop('compression', None)
        dtype = numpy.dtype(dtype) if dtype is not None else numpy.float32
        if shape and maxshape is None:
            raise TypeError("Need to specify shape or maxshape for dataset")
        if shape is None:
            shape = [(k if k else 0) for k in maxshape]
        if maxshape is None:
            maxshape = shape
        if chunks is None:
            chunks = make_chunks(maxshape, dtype, CHUNK_SIZE)
        if compression is None:
            size = numpy.prod([d for d in maxshape if d])*dtype.itemsize
            compression = 9 if size > CHUNK_SIZE else None
        elif compression == 'none':
            compression = None
        create_opts.update(shape=shape,maxshape=maxshape,dtype=dtype,
                           compression=compression,chunks=chunks)

    # Numeric data needs units
    if dtype.kind in ('u','i','f','c') and units is None:
        raise TypeError("Units required for numeric data at %r"%(node.name+"/"+path))

    # Label defaults to 'Field (units)'
    if label is None:
        name = " ".join(child.split('_')).capitalize()
        if units:
            label = "%s (%s)"%(name,units)
        else:
            label = name

    #print "create_opts", create_opts
    # Create the data
    try:
        dataset = node.create_dataset(child, **create_opts)
    except Exception,exc:
        _annotate_exception(exc,"when creating field %s"%path)
        raise
    attrs=attrs.copy()
    if units is not None:
        attrs['units'] = units
    if label: # not None or ""
        attrs['long_name'] = label
    for k,v in attrs.items():
        try:
            try: v = v.encode('UTF-8')
            except AttributeError: pass
            dataset.attrs[k] = v
        except Exception,exc:
            #print k,v
            _annotate_exception(exc,"when creating attribute %s@%s"%(path,k))
            raise
    return dataset

def append(node, data):
    """
    Append to a data node.

    Like list.append, this extends the node by one frame and writes
    the data to the end.  The data shape should match the shape of
    a single frame of the node, so it will have one fewer dimensions
    and data.shape[:] == node.shape[1:].

    Append is equivalent to::

        node.resize(node.shape[0]+1, axis=0)
        node[-1] = data
    """
    node.resize(node.shape[0]+1, axis=0)
    node[-1] = data

def extend(node, data):
    """
    Extend the data in the node.

    Like list.extend, this extends the node by as many frames as there
    are in the data and writes the data to the end.  The data shape should
    match the shape of a group of frames of the node, so it will have the
    same number of dimensions and data.shape[1:] == node.shape[1:].

    For more complicated operations, use node.resize to expand the
    data space then assign directly to the desired slice.
    """
    if len(data) > 0:
        node.resize(node.shape[0]+data.shape[0], axis=0)
        node[-data.shape[0]:-1] = data

def make_chunks(maxshape, dtype, min_chunksize):
    """
    Determine chunk size for storage.

    *maxshape* : [int, ...]
        The storage dimensions, with extensible dimensions indicated by None.
    *dtype* : numpy.dtype
        Storage type.
    *min_chunksize* : int
        Minimum size recommended for the chunk.
    """
    varying_idx = [i for i,v in enumerate(maxshape) if v is None]
    if varying_idx:
        chunks = [(v if v else 1) for v in maxshape] # Non-zero dims
        fixed_size = numpy.prod(chunks) * numpy.dtype(dtype).itemsize
        chunks[varying_idx[0]] = min_chunksize//fixed_size + 1
        chunks = tuple(chunks)
    else:
        chunks = None
    return chunks

def _name(node):
    return node.name.split("/")[-1]

def walk(node, topdown=True):
    """
    Walk an HDF-5 tree.

    Yields a sequence of (parent,groups,datasets).

    *node* is root of the tree, which should be an HDF-5 group.

    *topdown* is true if parent node should be visited before children.

    Like os.walk, groups can be modified during a topdown traversal to limit
    the set of groups visited.
    """
    #print "entering walk with",node
    if not isinstance(node, h5.Group):
        raise TypeError("must walk a group")
    groups, datasets = [],[]
    for n in node.values():
        if isinstance(n, h5.Dataset):
            datasets.append(n)
        elif isinstance(n, h5.Group):
            groups.append(n)
        else:
            raise TypeError("Expected group or dataset")
    if topdown:
        yield node, groups, datasets
        for g in groups:
            for args in walk(g, topdown=topdown): yield args
    else:
        for g in groups:
            for args in walk(g, topdown=topdown): yield args
        yield node, groups, datasets

def datasets(root):
    """
    Return all datasets within a node or any of its children.

    Each dataset is a list of paths which point to it.   For example,
    the average temperature at the sample may be linked to
    *DAS_logs/Temperature/average_value*, *sample/temperature*,
    *sample/temperature_env/average_value* and *data/temperature*.

    The datasets are not returned in any particular order.
    """
    datasets = {}
    links = root.file.id.links
    for node, _groups, fields in walk(root):
        for f in fields:
            # Save name since softlink handling chases down links
            linkname = f.name
            # Chase down link to a file location or an external file
            while True:
                linkinfo = links.get_info(f.name)
                if linkinfo.type == h5.h5l.TYPE_SOFT:
                    f = node[links.get_val(f.name)]
                    continue
                elif linkinfo.type == h5.h5l.TYPE_HARD:
                    location = linkinfo.u
                    break
                elif linkinfo.type == h5.h5l.TYPE_EXTERNAL:
                    location = links.get_value(f.name)
                    break
            # Return list associated with location, or create new one
            linkset = datasets.setdefault(location,[])
            # Add name to list
            linkset.append(linkname)
    return list(datasets.values())  # Return copy of items

def _simple_copy(source,target,exact=False):
    """
    copy a file from one location to another.

    this really should copy from one group to another but that is somewhat
    harder
    """
    rootlen = len(source.parent.name)+1
    for node, _groups, datasets in walk(source):
        relpath = node.name[rootlen:]
        # Copy group and attributes for parent
        # Subgroups will become parents in next iteration
        # Like os.walk, groups can be modi
        current = target.create_group(name=relpath)
        for k,v in node.attrs.iteritems():
            current.attrs[k] = v
        # Copy data and attributes for datasets
        for obj in datasets:
            name = obj.name.split('/')[-1]
            if exact:
                t = current.create_dataset(
                    name=name,
                    shape=obj.shape,
                    dtype=obj.dtype,
                    data=obj,
                    chunks=obj.chunks,
                    compression=obj.compression,
                    compression_opts=obj.compression_opts,
                    shuffle=obj.shuffle,
                    fletcher32=obj.fletcher32,
                    maxshape=obj.maxshape,
                    )
            elif obj.compression:
                t = current.create_dataset(
                    name=name,
                    shape=obj.shape,
                    dtype=obj.dtype,
                    data=obj,
                    chunks=obj.chunks,
                    compression=obj.compression,
                    compression_opts=obj.compression_opts,
                    shuffle=obj.shuffle,
                    fletcher32=obj.fletcher32,
                    #maxshape=obj.maxshape,
                    )
            else:
                t = current.create_dataset(
                    name=name,
                    data=obj,
                    )
            for k,v in obj.attrs.iteritems():
                t.attrs[k] = v

def tree(self, depth=1, attrs=True, indent=0):
    """
    Return the structure of the HDF 5 tree as a string.

    *group* is the starting group.

    *depth* is the number of levels to descend (default=2), or inf for full tree

    *attrs* is False if attributes should be hidden

    *indent* is the indent for each line.
    """
    return "\n".join(_tree_format(group, indent, attrs, depth))
# Add Tree attribute to h5py Group
h5.Group.tree = new.instancemethod(tree, None, h5.Group)


def _tree_format(node, indent, attrs, depth):
    """
    Return an iterator for the lines in a formatted HDF5 tree.

    Individual lines are not terminated by newline.
    """
    if not isinstance(node, h5.Group):
        raise TypeError("must walk a group")

    # Find fields and subgroups within the group; do this ahead of time
    # so that we can show all fields before any subgroups.
    groups, datasets = [],[]
    for n in node.values():
        if isinstance(n, h5.Dataset):
            datasets.append(n)
        elif isinstance(n, h5.Group):
            groups.append(n)
        else:
            raise TypeError("Expected group or dataset")

    # Yield group as "nodename(nxclass)"
    yield "".join( (" "*indent, _group_str(node)) )

    # Yield group attributes as "  @attr: value"
    indent += 2
    if attrs:
        for s in _yield_attrs(node, indent):
            yield s

    # Yield fields as "  field[NxM]: value"
    for field in datasets:
        #print field

        # Field name is tail of path
        name = field.name.split('/')[-1]

        # Short circuit links
        if 'target' in field.attrs and field.attrs['target'] != field.name:
            yield "".join( (" "*indent, name, " -> ", field.attrs['target']) )
            continue

        # Format field dimensions
        ndim = len(field.shape)
        if ndim > 1 or (ndim == 1 and field.shape[0] > 1):
            shape = '['+'x'.join( str(dim) for dim in field.shape )+']'
        else:
            shape = ''
        #shape = '['+'x'.join( str(dim) for dim in field.shape)+']'+str(field.dtype)

        # Format string or numeric value
        size = numpy.prod(field.shape)
        if str(field.dtype).startswith("|S"):
            if size == 0:
                value = '['*ndim + ']'*ndim
            elif ndim == 0:
                value = _limited_str(field.value)
            elif ndim == 1:
                if size == 1:
                    value = _limited_str(field.value[0])
                else:
                    value = _limited_str(field.value[0])+', ... '
                value = '['+value+']'
            else:
                value = '[[...]]'
        else:
            if size == 0:
                value = '['*ndim + ']'*ndim
            elif ndim == 0:
                value = "%g"%field.value
            elif ndim == 1:
                if size == 1:
                    value = "%g"%field.value[0]
                elif size <= 6:
                    value = ' '.join("%g"%v for v in field.value)
                else:
                    value =  ' '.join("%g"%v for v in field.value[:6]) + ' ...'
                value = '['+value+']'
            else:
                value = '[[...]]'

        # Yield field: value
        yield "".join( (" "*indent, name, shape, ': ', value) )

        # Yield attributes
        if attrs:
            for s in _yield_attrs(field, indent+2):
                yield s

    # Yield groups.
    # If recursive, show group details, otherwise just show name.
    if depth>0:
        for g in groups:
            for s in _tree_format(g, indent, attrs, depth-1):
                yield s
    else:
        for g in groups:
            yield "".join( (" "*indent, _group_str(g)) )

def _yield_attrs(node, indent):
    for k in sorted(node.attrs.keys()):
        if k not in ("NX_class", "target"):
            yield "".join( (" "*indent, "@", k, ": ", str(node.attrs[k])) )

def _group_str(node):
    if node.name == "/": return "root"
    nxclass = "("+node.attrs["NX_class"]+")" if "NX_class" in node.attrs else ""
    return node.name.split("/")[-1] + nxclass

def _limited_str(s):
    s = str(s).strip()
    ret = s.split('\n')[0][:40]
    return ret if len(ret) == len(s) else ret+"..."


# ==== Helper routines ====
def _get_path(node, path):
    """
    Return parent, child pair, where the entire parent path must exist.
    """
    parts = path.split('/')
    parentpath,child = "/".join(parts[:-1]), parts[-1]
    if parentpath:
        node = node[parentpath]
    return node,child

def _annotate_exception(exc, msg):
    args = exc.args
    if not args:
        arg0 = msg
    else:
        arg0 = " ".join((args[0],msg))
    exc.args = tuple([arg0] + list(args[1:]))


# ============= Test functions ==========

def test():
    from . import h5nexus

    # Sample data
    counts = [4, 2, 10, 45, 2150, 58, 6, 2, 3, 0]
    twotheta = numpy.arange(len(counts))*0.2+1.

    # Create the file
    nxs = h5nexus.open('writer_2_1.hdf5', 'w', driver='core', backing_store=False)
    entry = h5nexus.group(nxs, 'entry', 'NXentry')
    h5nexus.group(entry, 'data', 'NXdata')
    h5nexus.group(entry, 'instrument', 'NXinstrument')
    detector = h5nexus.group(nxs,'/entry/instrument/detector', 'NXdetector')
    h5nexus.field(detector, 'two_theta', data=twotheta, dtype="float32",
                units="degrees")
    h5nexus.field(detector, 'counts', data=counts, dtype="int32",
                units="counts", attrs={'signal': 1, 'axes': 'two_theta'})
    h5nexus.link(detector['two_theta'], '/entry/data/two_theta')
    h5nexus.link(detector['counts'], '/entry/data/counts')

    # Check that the data was written
    assert numpy.linalg.norm(numpy.array(counts)
                             - nxs['/entry/data/counts']) == 0
    assert numpy.linalg.norm(twotheta
                             - nxs['/entry/instrument/detector/two_theta']) <=1e-6

    # Search for unique datasets
    S = datasets(nxs)
    #print S
    assert len(S) == 2
    S1,S2 = set(S[0]),set(S[1])
    Gcounts = set(('/entry/data/counts','/entry/instrument/detector/counts'))
    G2theta = set(('/entry/data/two_theta','/entry/instrument/detector/two_theta'))
    assert (S1 == Gcounts and S2 == G2theta) or (S1 == G2theta and S2 == Gcounts)

    # All done
    nxs.close()

def main():
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "-a":
            files,attrs = sys.argv[2:],True
        else:
            files,attrs = sys.argv[1:],False
        for fname in files:
            h = open(fname, "r")
            print "===",fname,"==="
            print h.tree(attrs=attrs,depth=inf)
            h.close()
    else:
        print "usage: python -m nice.stream.nexus [-a] files"

if __name__ == "__main__": main()
