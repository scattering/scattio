# This program is public domain
"""
Neutron scattering file formats

=== File formats ===

Supported formats are:

     ICP on NCNR NG-1, CG-1 and NG-7

The list of available formats can be found at runtime using
data2nexus.formats.available()

Sample data for some of these formats is available in datadir.  In ipython
type the following:

    from data2nexus import formats
    ls $formats.datadir

=== Loading files ===

Data files are loaded using:

    data = formats.load('path/to/file')

This creates a NeXus data object in memory whose fields can be
accessed directly.  Note that some data formats can store multiple
measurements in the file, so the returned structure may contain
multiple NeXus entries.

=== Registering new formats ===

New formats can be created and register using

    formats.register(loader)

See the formats.register documentation for a description of the loader
function interface.
"""

import os.path
from .registry import ExtensionRegistry
__all__ = ['load','datadir']

datadir = os.path.join(os.path.dirname(__file__),'examples')


# Shared registry for all reflectometry formats
REGISTRY = ExtensionRegistry()

def load(filename, format=None):
    """
    Load the reflectometry measurement description and the data.

    Returns a single measurement if there is only one measurement in
    the filename, otherwise it returns a list of measurements.

    Use formats() to list available filename types for format.
    """
    return REGISTRY.load(filename, format=format)

def available():
    """
    Return a list of available file formats.
    """
    return REGISTRY.formats()

def register(ext,loader):
    """
    Register loader for a file extension.

    For each normal file extension for the format, call
        register('.ext',loader)
    You should also register the format name as
        register('name',loader)
    This allows the user to recover the specific loader using:
        load('path',format='name')

    The loader has the following signature:

        [data1, data2, ...] = loader('path/to/file.ext')

    The loader should raise an exception if file is not of the correct
    format.  When encountering an exception, load will try another loader
    in reverse order in which the they were registered.  If all loaders
    fail, the exception raised by the first loader will be forwarded to
    the application.

    The returned objects should support the ReflData interface and
    include enough metadata so that guess_intent() can guess the
    kind and extent of the measurement it contains.  The metadata need
    not be correct, if for example the length and the actual values of
    the motors are not known until the file is completely read in.

    After initialization, the application will make a call to data.load()
    to read in the complete metadata.  In order to support large datasets,
    data.detector.counts can use weak references.  In that case the
    file format should set data.detector.loadcounts to a method which
    can load the counts from the file.  If load() has already loaded
    the counts in it can set data.detector.counts = weakref.ref(counts)
    for the weak reference behaviour, or simply data.detector.counts = counts
    if the data is small.

    Both loader() and data.load() should call the self.resetQ() before
    returning in order to set the Qx-Qz values from the instrument geometry.

    File formats should provide a save() class method.  This method
    will take a ReflData object plus a filename and save it to the file.
    """
    REGISTRY[ext] = loader

# Delayed loading of file formats
def icp_ng7(file):
    """NCNR NG-7 ICP file loader"""
    from .ng7convert import convert
    return convert(file, ":entry")

def icp_ng1(file):
    """NCNR NG-7 ICP file loader"""
    from .ng1convert import convert
    return convert(file, ":entry")

def nexus(file):
    """NeXus file loader"""
    from h5py import File
    return File(file, 'r')

def vax_sans(file):
    """NCNR SANS VAX file loader"""
    from .sansconvert import convert
    return convert(file, ":entry")

def ice_bt7(file):
    """NCNR BT-7 ICE file loader"""
    from .bt7convert import convert
    return convert(file, ":entry")

# Register extensions with file formats
register('.ng7', icp_ng7)
register('.ng7.gz', icp_ng7)
register('NCNR NG-7',icp_ng7)

register('.nxs', nexus)
register('NeXus', nexus)

register('NCNR NG-1', icp_ng1)
register('.[nc][abcdg]1', icp_ng1)
register('.[nc][abcdg]1.gz', icp_ng1)

register('NCNR SANS', vax_sans)
register('.SA[123]*', vax_sans)

register('NCNR BT-7', ice_bt7)
register('.bt7', ice_bt7)

def test():
    from .utils import example

    # make sure we've defined the various file formats
    assert set(available()) == set(['NCNR NG-1','NCNR NG-7','NCNR SANS','NCNR BT-7','NeXus']),available()

    # check that examples are found and loaded; don't check that they have
    # correct content since that will be done by individual loader tests
    ng7file = load(example('ng7','jul04031.ng7'))
    wavelength = ng7file["/entry/instrument/monochromator/wavelength"].value/10
    assert (wavelength-0.476) < 1e-6  # float32(4.76)/10 is not exactly 0.476

    #ng1file = example('ng1','psih1001.ng1')
    #assert load(ng1file).name == 'gsip4007.ng1'

    #cg1file = example('cg1area','psdca022.cg1.gz')
    #assert loadmeta(cg1file).name == 'psdca022.cg1'

    sansfile = os.path.join(datadir,'sans','SILIC001.SA3_SRK_S101')
    assert load(sansfile)["/entry/file_name"].value == 'SILIC001.SA3_SRK_S101'

    bt7file = example('bt7','201102-16363-largeq_90397.bt7')
    assert load(bt7file)["/entry/file_name"].value == 'largeq_90397'


if __name__ == "__main__": test()
