"""
Load NG-7 icp data as nexus
"""
__all__ = ['load']

import os
import numpy

from . import jsonutil
from . import icpformat
from . import qxqz
from .utils import format_timestamp, template
from .qxqz import neutron_energy
from .write_nexus import write_nexus, main_driver

_NG7_TO_NICE = {
    'date': 'trajectory.start',
    'filename': 'trajectory.filename',
    'comment': 'trajectory.title',
    'program': 'trajectory.programName',
    'run': 'trajectory.sequence',
    'monitor': 'counter.liveMonitor',
    'time': 'counter.liveTimer',
    'count_mode': 'counter.countAgainst',
    's1': 'slit1.softPosition',
    's2': 'slit2.softPosition',
    's3': 'slit3.softPosition',
    's4': 'slit4.softPosition',
    'qx': 'q.x',
    'qz': 'q.z',
    'counts': 'pointDetector.counts',
    'psd': 'areaDetector.counts',
    'temperature': 'temperature.sensor',
    'Hfield': 'magnet.field',
    }

# Units to use for each motor that users might scan.
_UNITS = {
    '1': '',
    '2': '',
    '10': '',
    '12': '',
    '13': '',
    '14': '',
    '20': '',
    'qx': '1/Angstrom',
    'qz': '1/Angstrom',
    's1': 'mm',
    's2': 'mm',
    's3': 'mm',
    's4': 'mm',
    'temp': 'C',
    'h-field': 'T',
    }

# If wavelength seems to be stored incorrectly in the file, the icpformat
# loader will ask the user if the stored value should be used or the default
# value; WAVELENGTH_OVERRIDES remembers for each dataset what value to use.
WAVELENGTH_OVERRIDES = {}


def convert(infile, outfile=None):
    """
    Convert NG-7 ICP data to NeXus.
    """
    data = icpformat.read(infile)
    nicedata = ng7_icp_to_nice(data)
    nexus_layout = jsonutil.relaxed_load(template("ng7nxs.json"))
    #import pprint; pprint.pprint(nexus_layout)
    if not outfile:
        outfile = os.path.basename(os.path.splitext(infile)[0]) + ":entry"
    return write_nexus(outfile, nicedata, nexus_layout)

def ng7_icp_to_nice(data):
    """
    Convert NCNR NG-7 ICP names to NICE names.
    """

    nicedata = {}
    def F(name, value, units=None, shortname=None):
        if shortname == None:
            shortname = name
        key = _NG7_TO_NICE.get(name, name)
        nicedata[key] = {'value':value, 'units':units, 'shortname': shortname}

    # == metadata ==
    F('date',format_timestamp(data.date))
    F('filename',data.filename)
    F('comment',data.comment)
    F('program','ICP')
    F('run', data.filename[:5])

    # == monitor data ==
    monitor_counts = count_time = None
    if "qz" in data:
        # NG7 automatically increases count times as Qz increases
        monitor, prefactor = data.monitor,data.prefactor
        Mon1, Exp = data.Mon1,data.Exp
        Qz = data.column.qz
        automonitor = prefactor*(monitor + Mon1 * abs(Qz)**Exp)
        if data.count_type == "NEUT":
            monitor_counts = automonitor
        elif data.count_type == "TIME":
            count_time = automonitor
        else:
            raise ValueError("Expected count type 'NEUT' or 'TIME' in "
                             + data.filename)
    if "monitor" in data:
        monitor_counts = data.column.monitor
    if "time" in data:
        count_time = data.column.time*60
    ## Don't compute duration of measurement since we can't account for
    ## dead time between points
    #self.duration = numpy.sum(count_time)

    if monitor_counts is not None:
        F('monitor',monitor_counts,'')
    if count_time is not None:
        F('time',count_time,'second')
    F('count_mode', "monitor" if data.count_type=="NEUT" else "timer")

    # == detector ==
    if data.PSD:
        F('counts', data.counts, '')
    else:
        F('psd', data.counts, '')

    # == wavelength/energy ==
    std = 0.025/2.35 # 2.5% FWHM wavelength spread expressed as 1-sigma error
    # This spread is small enough that it is accurate for E ~ 1/lambda as well.
    default_wavelength = 4.76
    wavelength = data.check_wavelength(default_wavelength, WAVELENGTH_OVERRIDES)
    F('monochromator.wavelength', wavelength, "Angstrom")
    F('monochromator.wavelengthSpread', wavelength*std, "Angstrom")
    F('monochromator.wavelength',neutron_energy(wavelength),"meV")
    F('monochromator.energySpread',neutron_energy(wavelength)*std,"meV")


    # == angles ==
    if "qz" in data:
        Qx = data.column.qx if "qx" in data else 0
        Qz = data.column.qz
        A,B = qxqz.QxQzL_to_AB(Qx,Qz,wavelength)
        #F('qx.softPosition',Qx,'1/Angstrom')
        #F('qz.softPosition',QZ,'1/Angstrom')
        F('a3.softPosition',A,'degrees')
        F('a4.softPosition',B,'degrees')

    # == sample environment ==
    if "temp" in data.columnnames:
        temperature = data.column.temp
    elif data.Tstep != 0:
        temperature = numpy.arange(data.points)*data.Tstep + data.Tstart
    else:
        temperature = data.Tstart
    F('temperature', temperature, "C")
    F('Hfield', data.Hfield, "T")

    # == DAS ==
    # All measured columns are stored in DASlogs
    for c in data.columnnames:
        if c not in ("monitor", "counts", "counts2"):
            F((c if not c[0].isdigit() else 'motor'+c)+".softPosition", 
              data.column[c],
              _UNITS.get(c,''))


    return nicedata

def test():
    """
    Make sure we can read an ng7 file as a nexus format tree structure.
    """
    from .utils import example
    ng7file = convert(example('ng7','jul04031.ng7'),':entry')
    wavelength = ng7file["/entry/instrument/monochromator/wavelength"].value/10
    assert (wavelength-0.476) < 1e-6  # float32(4.76)/10 is not exactly 0.476

if __name__ == "__main__":
    main_driver(convert)

## Use unix tools to identifier motors that people use
# find . -name "*.ng7" | grep -v fpx | xargs grep -h -A1 Mot: | grep -v "Mot:" | sort | uniq
# 10          MON    #1 COUNTS   #2 COUNTS
# 12          MON    #1 COUNTS   #2 COUNTS
# 12    S1    S2    S3          MON    #1 COUNTS   #2 COUNTS
# 12    S2          MON    #1 COUNTS   #2 COUNTS
# 12     TEMP         MON    #1 COUNTS   #2 COUNTS
# 13          MON    #1 COUNTS   #2 COUNTS
# 13    S1    S2    S3          MON    #1 COUNTS   #2 COUNTS
# 13     TEMP         MON    #1 COUNTS   #2 COUNTS
# 14          MON    #1 COUNTS   #2 COUNTS
# 20    S1    S2    S3           MON    #1 COUNTS   #2 COUNTS
#  2          MON    #1 COUNTS   #2 COUNTS
#        MON    #1 COUNTS   #2 COUNTS
#     QZ     10    S1    S2          MON    #1 COUNTS   #2 COUNTS
#     QZ     13          MON    #1 COUNTS   #2 COUNTS
#     QZ     13    S1    S2          MON    #1 COUNTS   #2 COUNTS
#     QZ     13    S1    S2      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNT
#     QZ     13    S1    S2      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNTS
#     QZ     13    S1    S2     TEMP         MON    #1 COUNTS   #2 COUNTS
#     QZ      1    S1    S2          MON    #1 COUNTS   #2 COUNTS
#     QZ           MON    #1 COUNTS   #2 COUNTS
#     QZ        QX     S1    S2          MON    #1 COUNTS   #2 COUNTS
#     QZ     S1    S2          MON    #1 COUNTS   #2 COUNTS
#     QZ     S1    S2    S3          MON    #1 COUNTS   #2 COUNTS
#     QZ     S1    S2    S3      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNT
#     QZ     S1    S2    S3      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNTS
#     QZ     S1    S2    S3     TEMP         MON    #1 COUNTS   #2 COUNTS
#     QZ     S1    S2    S4           MON    #1 COUNTS   #2 COUNTS
#     QZ     S1    S2      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNTS
#     QZ     S1    S2     TEMP         MON    #1 COUNTS   #2 COUNTS
#     QZ     S2          MON    #1 COUNTS   #2 COUNTS
#     QZ     S3          MON    #1 COUNTS   #2 COUNTS
#     QZ      TEMP         MON    #1 COUNTS   #2 COUNTS
# S1          MON    #1 COUNTS   #2 COUNTS
# S1    S2          MON    #1 COUNTS   #2 COUNTS
# S1    S2    S3          MON    #1 COUNTS   #2 COUNTS
# S1    S2    S3    S4          MON    #1 COUNTS   #2 COUNTS
# S1    S2    S3    S4      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNTS
# S1    S2    S3    S4     TEMP         MON    #1 COUNTS   #2 COUNTS
# S1    S2    S3     TEMP         MON    #1 COUNTS   #2 COUNTS
# S1    S2      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNTS
# S2          MON    #1 COUNTS   #2 COUNTS
# S2    S3          MON    #1 COUNTS   #2 COUNTS
# S2    S3    S4          MON    #1 COUNTS   #2 COUNTS
# S2    S3    S4      TEMP   H-FIELD       MON    #1 COUNTS   #2 COUNTS
# S3          MON    #1 COUNTS   #2 COUNTS
#   TEMP         MON    #1 COUNTS   #2 COUNTS
