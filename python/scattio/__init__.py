"""
Data readers for various scattering data file formats.

NeXus readers
=============

Data can be read as a NeXus file using the load function::

    >>> from nice import reader
    >>> ng7file = reader.load(reader.example('ng7','jul04031.ng7'))

The `NeXus standard <http://nexusformat.org>`_ defines names for describing 
components of neutron, muon and X-ray beamlines including source, sample and 
detectors.  The format is extensible and self describing.  Values are stored 
along with units.  Static data, such as the dimensions of the beamline 
components, that are not directly controlled by the instrument control 
software can be stored.  Not all information required to analyze the 
measurement will be known in advance, but there is a place to store what 
is known.  Multiple datasets can be stored in different entries in the
same data file, and links can be made between data files.  For example, all 
the measurements needed for a single SANS reduction (measurements of scattering
at various distances, measurement of the transmission, measurement of the
empty cell, measurement of the dark current and detector calibration
measurements could be stored together, or possibly in two files with links
between them.
    
Individual fields are accessed using the 
`h5py <http://code.google.com/p/h5py/>`_ interface, even if the files were 
not originally stored in HDF5 format.  This high level interface allows simple 
access to the instrument data and attributes::
    
    >>> print ng7file["/entry/instrument/monochromator/wavelength"].value
    4.76
    >>> print ng7file["/entry/instrument/monochromator/wavelength"].attrs["units"]
    Angstrom

Data can also be access using relative paths::

    >>> mono = ng7file["/entry/instrument/monochromator"]
    >>> print mono["wavelength"].value
    4.76

Because the units are stored with the data, we do not need to know how they
are stored for data reduction, but can convert them to the units needed for
the reduction calculation.  For example, wavelength can be read as nanometers
instead of Angstroms::

    >>> print reader.data_as(mono["wavelength"],"nm")
    0.476

The complete file structure can be displayed with the h5nexus summary command::

    >>> scattio.h5nexus import summary
    >>> summary(ng7file)
    
This will work on any sub-tree as well::

    >>> summary(mono)

The NeXus standard is somewhat unwieldy since it describes a broad range 
of instrumentation and experiment styles across many independent institutions.  
Even for  instruments which are fundamentally similar, differences in data 
acquisition systems have inevitably lead to multiple ways to represent the same
information within the standard, and the standard is not always adhered to.
Reduction software will likely require tweaks to support data from different
instruments, particularly if they are measured at different facilities.

NeXus converters
================

For each instrument there is a converter from the raw format to the NeXus
namespace.  The instrument details that are not stored in the original file,
such as the distance between source aperture and sample, are defined in a JSON
mapping file, which by  convention is named zzznxs.json for instrument zzz.
As of this writing we have the following converters:

:mod:`ng7convert`

    NG-7 reflectometer
    
:mod:`bt7convert`

    BT-7 spectrometer
    
:mod:`sansconvert`

    NG-3, NG-5 and NG-7 SANS spectrometers.
    
These converters can be run standalone using::

    $ python -m nice.reader.zzzconvert [-o path:entry] files...

The path:entry argument allows you to define the filename and entry where the
converted data will live.  Values from the datafile can be used to define
path or entry by embedding "<group.field>" in the name.  This will substitute
the value of "/entry/DASlogs/group/file" into the name.  The group and field
names are arbitrary and defined by the individual format conversion functions.
These are the same names used in the instrument to NeXus JSON mapping files.
The source for the conversion programs will contain a map from the raw
format names into these names.

Raw data access
===============

Various raw format readers are available:

:mod:`iceformat`

    Columnar ASCII format for NCNR BT-7 created by ICE control software.

:mod:`icpformat`

    ASCII format for NCNR reflectometers (NG-1, NG-7, CG-1) and triple
    axis spectrometers (BT-4, BT-9) created by ICP control software.

:mod:`sansformat`

    Binary format for NCNR SANS spectrometers (NG-3, NG-5, NG-7) with
    VAX floating point representation.

These readers preserve the namespace of the original file format.  There is
little consistency between the interfaces.
"""

from formats import load
from utils import example, data_as
