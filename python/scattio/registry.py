# This program is public domain
"""
File extension registry.

This provides routines for opening files based on extension,
and registers the built-in file extensions.


Example
=======

Create the registry and define some formats::

    >>> registry = ExtensionRegistry()

Define some file loaders.  You are free to define what the loaders
return, but it should be consistent.  For example, if some formats
can handle multiple datasets, all formats should return a list
of datasets.  We use the following fake loaders in the examples that
follow::

    >>> def cx1(): return 'cx1'
    >>> def cx2(): return 'cx2'
    >>> def cx3(): return 'cx3'
    >>> def sans(): return 'sans'
    >>> def gunzip(): return 'gunzip'
    >>> def untar(): return 'untar'

Loaders are associated with file extensions by assigning to the
dictionary element::

    >>> registry['.zip'] = unzip

Unlike a normal dictionary, though, the assignment operator acts
like a list append.  This allows multiple loaders to be associated
with a single extension::

    >>> registry['.cx'] = cx1
    >>> registry['.cx'] = cx2
    >>> registry['.cx'] = cx3

Extensions can use glob patterns::

    >>> registry['.SA[123]*'] = sans

Note that the extension need not start with '.' if '*' is used in
the pattern.

A single loader can be associated with multiple extensions::

    >>> registry['.tgz'] = untar
    >>> registry['.tar.gz'] = untar

Loaders are tried in order of decreasing pattern length.  The first
loader than can retrieve the file without raising an error is the
winner.  For example, if we add the following::

    >>> registry['.gz'] = gunzip

and try to load the file "data.tar.gz", then the *untar* loader will
be tried before the *gunzip* loader.

The list of registered extensions can be displayed::

    >>> print registry.extensions()
    [ '.SA[123]*', '.cx', '.gz', '.tar.gz', '.tgz', '.zip' ]

Formats can also be named, allowing for explicit control from caller
Format names differ from extensions in that they do not have a 
leading '.' or a '*' anywhere in them.  In the following case, since
*cx3* is the only named format, it will be the only one returned from
registry.formats::

    >>> registry['CX3 format'] = cx3
    >>> print registry.formats()
    [ 'CX3 format' ]

To load a file, you simply call registry.load with the filename.
For example::

    >>> registry.load('hello.cx')
    'cx1'

This is equivalent to::

    for format in cx1, cx2, cx3:
        try:    return format('hello.cx')
        except: pass
    raise

This returns the results for the first loader which can load the file.
If all the loaders fail, then the exception for the most general loader
is re-raised.

The list of formats to try is given by registry.lookup::

    >>> print registry.lookup('hello.cx')
    [ cx1, cx2, cx3 ] 

If you know the format, you can use the loader directly, ignoring the
filename.  For example::

    >>> registry.load('hello.cx',format='CX3 format')
    'cx3'

This could be used, for example, to present the list of available formats
returned by registry.formats to the user, and have them choose which
format to use, or None for the default based on file extension.
"""

import fnmatch

class ExtensionRegistry(object):
    """
    Associate file loaders with file extensions.
    """
    def __init__(self):
        self.loaders = {}

    def __setitem__(self, ext, loader):
        self.loaders.setdefault(ext,[]).append(loader)

    def __getitem__(self, ext):
        return self.loaders[ext]

    def __contains__(self, ext):
        return ext in self.loaders

    def formats(self):
        """
        Return a sorted list of the registered formats.
        """
        names = [a for a in self.loaders.keys() 
                 if not a.startswith('.') and "*" not in a]
        names.sort()
        return names

    def extensions(self):
        """
        Return a sorted list of registered extensions.
        """
        exts = [a for a in self.loaders.keys() 
                if a.startswith('.') or "*" in a]
        exts.sort()
        return exts

    def lookup(self, path):
        """
        Return the loaders associated with the file name.

        Raises ValueError if file type is not known.
        """
        # Find matching extensions
        extlist = [ext for ext in self.extensions()
                   if fnmatch.fnmatch(path, '*'+ext)]

        # Sort matching extensions by decreasing order of length
        extlist.sort(lambda a,b: len(a)<len(b))

        # Combine loaders for matching extensions into one big list
        loaders = []
        for L in [self.loaders[ext] for ext in extlist]:
            loaders.extend(L)

        # Remove duplicates if they exist
        if len(loaders) != len(set(loaders)):
            result = []
            for L in loaders:
                if L not in result: result.append(L)
            loaders = result

        # Raise an error if there are no matching extensions
        if len(loaders) == 0:
            raise ValueError, "Unknown file type for "+path

        # All done
        return loaders

    def load(self, path, format=None):
        """
        Try loading all datasets from the given path.  If no format is
        specified, try all formats which match the path extension.

        Raises ValueError if no loader is available
        Raises KeyError if format is not available.
        Raises a loader-defined exception if all loaders fails.
        """
        if format is None:
            loaders = self.lookup(path)
        else:
            loaders = self.loaders[format]
        for fn in loaders:
            try:
                return fn(path)
            except:
                pass # give other loaders a chance to succeed
        # If we get here it is because all loaders failed
        raise # reraises last exception

def test():
    reg = ExtensionRegistry()
    class CxError(Exception): pass
    def cx(filename): return 'cx'
    def new_cx(filename): return 'new_cx'
    def fail_cx(filename): raise CxError
    def cat(filename): return 'cat'
    def gunzip(filename): return 'gunzip'
    reg['.cx'] = cx
    reg['.cx1'] = cx
    reg['.cx'] = new_cx
    reg['.gz'] = gunzip
    reg['.cx.gz'] = new_cx
    reg['.cx1.gz'] = fail_cx
    reg['.cx1'] = fail_cx
    reg['.cx2'] = fail_cx
    reg['new_cx'] = new_cx

    # Two loaders associated with .cx
    assert reg.lookup('hello.cx') == [cx, new_cx]
    # Make sure the last loader applies first
    assert reg.load('hello.cx') == 'cx'
    # Make sure the next loader applies if the first fails
    assert reg.load('hello.cx1') == 'cx'
    # Make sure the format override works
    assert reg.load('hello.cx1',format='.cx.gz') == 'new_cx'
    # Make sure the format override works
    assert reg.load('hello.cx1',format='new_cx') == 'new_cx'
    # Make sure the case of all loaders failing is correct
    try:  reg.load('hello.cx2')
    except CxError: pass # correct failure
    else: raise Exception("Incorrect error on load failure")
    # Make sure the case of no loaders fails correctly
    try: reg.load('hello.missing')
    except ValueError,msg:
        assert str(msg)=="Unknown file type for hello.missing",'Message: <%s>'%(msg)
    else: raise Exception("No error raised for missing extension")
    assert reg.formats() == ['new_cx']
    assert reg.extensions() == ['.cx','.cx.gz','.cx1','.cx1.gz','.cx2','.gz']
    # make sure that it supports multiple '.' in filename
    assert reg.load('hello.extra.cx1') == 'cx'
    assert reg.load('hello.gz') == 'gunzip'
    assert reg.load('hello.cx1.gz') == 'gunzip' # Since .cx1.gz fails

if __name__ == "__main__": test()
