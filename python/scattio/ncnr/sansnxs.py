import os
import numpy

from . import sansformat
from . import jsonutil
from .utils import template
from .utils import format_timestamp
from .write_nexus import write_nexus, main_driver

_SANS_TO_NICE = {
    'fname.filename': 'trajectory.filename', #   2  filename
     
    'run.npre': 'counter.prefactor', #  23  number of run prefactors
    'run.ctime': 'counter.prefactorTime', #  27  count time per prefactor (s)
    'run.rtime': 'counter.liveTimer', #  31  total count time (s)
    'run.numruns': '', #  35
    'run.moncnt': 'counter.liveMonitor', #  39  monitor count
    'run.savmon': '', #  43
    'run.detcnt': 'counter.liveROI', #  47  detector count (from the anode plane)
    'run.atten': 'attenuator.index', #  51  attenuator number (not transmission)
    'run.datetime': 'trajectory.date', #  55  data and time of collection DD-MMM-YYYY HH:MM:SS
    'run.type': '', #  75  'RAW'
    'run.defdir': '', #  78  NGxSANSnn
    'run.mode': '', #  89  C, M
    'run.reserve': '', #  90  DDMMMYY (another date prob. not needed)

    'sample.labl': 'sample.sampleName', #  98  sample label
    'sample.trns': 'sample.transmission', # 158  sample transmission
    'sample.thk': 'sample.thickness', # 162  sample thickness (cm)
    'sample.position': 'sampleChanger.index', # 166  sample changer position
    'sample.rotang': 'sample.rotation', # 170  sample rotation angle (degrees)
    'sample.table': 'sampleChanger.softPosition', # 174  chamber or huber position
    'sample.holder': 'sampleChanger.name', # 178  sample holder identifier
    'sample.blank': '', # 182
    'sample.temp': 'temperature.sensor', # 186  temperature (sample.tunits)
 # IGOR code says field strength for the electromagnets is at 348
    'sample.field': '', # 190  applied field strength (sample.funits)
    'sample.tctrlr': '', # 194  sample control identifier
    'sample.magnet': '', # 198  magnet identifier
    'sample.tunits': '', # 202  temperature units
    'sample.funits': '', # 208  applied field units

    'det.typ': 'areaDetector.type', # 214  ORNL or ILL
    'det.calx1': '', # 220  detector x pixel size (mm)
    'det.calx2': '', # 224  non-linear spatial (10000)
    'det.calx3': '', # 228  corrections (0)
    'det.caly1': '', # 232  detector y pixel size (mm)
    'det.caly2': '', # 236  (10000)
    'det.caly3': '', # 240  (0)
    'det.num': '', # 244  area detector identifier
    'det.spacer': '', # 248
    'det.beamx': '', # 252  beam center x position (detector coord)
    'det.beamy': '', # 256  beam center y position (detector coord)
    'det.dis': '', # 260  sample to detector distance (m)
    'det.ang': '', # 264  horizontal detector offset (cm)
    'det.siz': '', # 268  physical detector width (cm)
    'det.bstop': '', # 272  beam stop diameter (mm)
    'det.blank': '', # 276
     
    'resolution.ap1': 'sourceAperture.softPosition', # 280  source aperture diameter (mm)
    'resolution.ap2': 'sampleAperture.softPosition', # 284  sample aperture diameter (mm)
    'resolution.ap12dis': '', # 288  source aperature to sample aperture distance (m)
    'resolution.lmda': 'monochromator.wavelength', # 292  wavelength (A)
    'resolution.dlmda': 'monochromator.wavelengthSpread', # 296  wavelength spread (FWHM)
    'resolution.save': '', # 300  lens flag
     
    'tslice.slicing': '', # 304
    'tslice.multfact': '', # 308  multiplicative factor for slicing bins
    'tslice.ltslice': '', # 312
     
    'temp.printemp': '', # 316  print temp after prefactor
    'temp.hold': '', # 320
    'temp.err': '', # 324
    'temp.blank': '', # 328
    'temp.extra': '', # 332  (0x0001 print blue box temp; 0x0100 control from int. bath or ext. probe)
    'temp.reserve': '', # 336
     
    'magnet.printmag': '', # 340
    'magnet.sensor': '', # 344
    'magnet.current': 'magnet.field', # 348
    'magnet.conv': '', # 352
    'magnet.fieldlast': '', # 356
    'magnet.blank': '', # 360
    'magnet.spacer': '', # 364
     
    'bmstp.xpos': '', # 368  beam stop X position (MCU app. cm)
    'bmstp.ypos': '', # 372  beam stop Y position (MCU app. cm)
     
    'params.blank1': '', # 376
    'params.blank2': '', # 380
    'params.blank3': '', # 384
    'params.trsncnt': '', # 388  transmission detector count
    'params.extra1': '', # 392  whole detector transmission
    'params.extra2': '', # 396
    'params.extra3': '', # 400
    'params.reserve': '', # 404  first four characters are associated file suffix
     
    'voltage.printvolt': '', # 446
    'voltage.volts': '', # 450 field strength for the superconducting magnet
    'voltage.blank': '', # 454
    'voltage.spacer': '', # 458
     
    'polarization.printpol': '', # 462
    'polarization.flipper': '', # 466
    'polarization.horiz': '', # 470
    'polarization.vert': '', # 474
     
    'analysis.rows1': '', # 478  box x1  (user defined tranmsission est. box)
    'analysis.rows2': '', # 482  box x2
    'analysis.cols1': '', # 486  box y1
    'analysis.cols2': '', # 490  box y2
    'analysis.factor': '', # 494  box counts
    'analysis.qmin': '', # 498
    'analysis.qmax': '', # 502
    'analysis.imin': '', # 506
    'analysis.imax': '', # 510
    
    # Fields not part of the SANS file header
    'program': 'trajectory.programName',
    'version': 'trajectory.programVersion',
    'sequence': 'trajectory.sequence',
    'counts': 'areaDetector.counts',
    }

def convert(infile, outfile=None):
    """
    Load BT-7 ICE data as a nexus in-memory structure.
    """
    counts, header = sansformat.readNCNRData(infile)
    nicedata = ncnr_sans_to_nice(counts, header)
    nexus_layout = jsonutil.relaxed_load(template("sansnxs.json"))
    #import pprint; pprint.pprint(nexus_layout)
    if not outfile:
        outfile = os.path.basename(os.path.splitext(infile)[0]) + ":entry"
    return write_nexus(outfile, nicedata, nexus_layout)

def ncnr_sans_to_nice(counts, header):
    """
    Convert NCNR sans data to NeXus.
    """
    data = header.copy()
    data['program'] = "ICE"
    data['counts'] = counts
    data['sequence'] = data['fname.filename'][:4]
    nicedata = dict((nicekey, {'value': data[key], 
                               'units': sansformat.INFO.units.get(key, ''), 
                               'precision': sansformat.INFO.precision.get(key, 0.01),
                               #'shortname': rename_field(nicekey),
                              })
                    for key,nicekey in _SANS_TO_NICE.items()
                    if key in data and nicekey)
    return nicedata

if __name__ == "__main__":
    main_driver(convert)
