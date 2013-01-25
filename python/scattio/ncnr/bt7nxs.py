#!/usr/bin/env python
"""
Convert BT-7 ICE data to nexus
"""
__all__ = ['convert']

import os
import re

import numpy

import iso8601
import h5nexus

from . import jsonutil
from . import iceformat
from .utils import format_timestamp, template
from .write_nexus import write_nexus, main_driver

# FIXME: these names need to be kept in sync with the names used in bt7.json
_ICE_TO_NICE = {
    'InstrumentName': 'experiment.instrument',
    'Filename': 'trajectory.filename',
    'Date': 'trajectory.date',
    'Epoch': '',
    'Comment': '',
    'ExptID': 'experiment.proposalId',
    'ExptName': 'experiment.name',
    'ExptDetails': 'experiment.description',
    'ExptParticpants': 'experiment.participants',
    'ExptComment': 'experiment.comment',
    'ScanDescr': 'icescan.description',
    #'ScanRanges': 'icescan.ranges',
    'Npoints': 'icescan.npoints',
    'ScanId': 'icescan.scanid',
    'ScanVarying': 'icescan.varying',
    'ScanTitle': 'icescan.title',
    'ScanComment': 'icescan.comment',
    'ScanBasename': 'icescan.basename',
    'ScanType': 'icescan.type',
    'Reference': '',
    'Signal': '',
    'Scan': '',
    'Fixed': '',
    'Lattice': 'sample.lattice',
    'Orient1': 'sample.orient1',
    'Orient2': 'sample.orient2',
    'TemperatureUnits': '',
    'FixedE': 'deltaE.base',
    'AnalyzerDetectorMode': '',
    'AnalyzerDetectorDevicesOfInterest': '',
    'AnaSpacing': 'ef.dSpacing',
    'AnalyzerFocusMode': 'analyzer.focus',
    'AnalyzerSDGroup': '',
    'AnalyzerPSDGroup': '',
    'AnalyzerDDGroup': '',
    'AnalyzerDoorDetectorGroup': '',
    'PostAnaCollType': 'postAnaColl.type',
    'PostAnaCollDivergence': 'postAnaColl.divergence',
    'MonoVertiFocus': 'mono.verticalFocus',
    'MonoHorizFocus': 'mono.horizontalFocus',
    'MonoSpacing': 'ei.dSpacing',
    'PreMonoCollType': 'preMonoColl.type',
    'PreMonoCollDivergence': 'preMonoColl.divergence',
    'ICE': '',
    'ICERepositoryInfo': '',
    'User': '',
    'UBEnabled': '',
    'Columns': '',
    'Ncolumns': '',
    'DetectorDims': '',
    'DetectorEfficiencies': '',
    'A1': 'a1.softPosition',
    'A2': 'a2.softPosition',
    'A3': 'a3.softPosition',
    'A4': 'a4.softPosition',
    'A5': 'a5.softPosition',
    'A6': 'a6.softPosition',
    'QX': 'q.x',
    'QY': 'q.y',
    'QZ': 'q.z',
    'H': 'hkl.h',
    'K': 'hkl.k',
    'L': 'hkl.l',
    'HKL': '',
    'Ei': 'ei.energy',
    'Ef': 'ef.energy',
    'E': 'deltaE.energy',
    'Time': 'counter.liveTimer',
    'Monitor': 'counter.liveMonitor',
    'Monitor2': '',
    'Detector': 'counter.liveROI',
    'TimeStamp': '',
    'MonoElev': 'mono.elev',
    'DFMRot': '',
    'DFM': 'mono.rotation',
    'MonoTrans': 'mono.trans',
    'MonoBlades': 'monoBlades.softPosition',
    'FocusCu': 'mono.focusCu',
    'FocusPG': 'mono.focusPG',
    'AnalyzerRotation': 'ana.rotation',
    'AnalyzerBlades': 'analyzerBlades.softPosition',
    'SmplGFRot': 'ana.smlGFRot',
    'SingleDet': 'backend.singleDetectorAngle',
    'DiffDet': 'backend.diffractionDetectorAngle',
    'PSDet': 'backend.psdAngle',
    'FilRot': 'filterRotation.softPosition',
    'FilTilt': 'filterTilt.softPosition',
    'FilTran': 'filterControl.enumValue',
    'ApertVert': 'preMonoSlit.height',
    'ApertHori': 'preMonoSlit.width',
    'SmplHght': 'preSampleSlit.height',
    'SmplWdth': 'preSampleSlit.width',
    'BkSltHght': 'preAnaSlit.height',
    'BkSltWdth': 'preAnaSlit.width',
    'PreMonoColl': '',
    'PostMonoColl': '',
    'PreAnaColl': '',
    'PostAnaColl': '',
    'RC': 'backend.radialCollimatorAngle',
    'SC': 'backend.sollerCollimatorAngle',
    'SmplElev': 'goniometer.elevation',
    'SmplLTilt': 'goniometer.lTilt',
    'SmplLTrn': 'goniometer.lTranslation',
    'SmplUTilt': 'goniometer.uTilt',
    'SmplUTrn': 'goniometer.uTranslation',
    'Temp': 'temperature.sensor',
    'MagField': 'magnet.field',
    'Pressure': 'pressureChamber.pressure',
    'TemperatureSetpoint': 'temperature.setpoint',
    'TemperatureHeaterPower': 'temperature.heaterPower',
    'TemperatureControlReading': 'temperature.controlReading',
    'TemperatureSensor0': 'temperature.sensor0',
    'TemperatureSensor1': 'temperature.sensor1',
    'TemperatureSensor2': 'temperature.sensor2',
    'TemperatureSensor3': 'temperature.sensor3',
    'Flip': 'polarization.enumValue',
    'Hsample': 'hField.field',
    'Vsample': 'vField.field',
    'EIcancel': 'frontPol.cancelCurrent',
    'EFcancel': 'backPol.cancelCurrent',
    'EIflip': 'frontPol.flipperCurrent',
    'EFflip': 'backPol.flipperCurrent',
    'EIguide': 'frontPol.guideCurrent',
    'EFguide': 'backPol.guideCurrent',
    'SDC': 'singleDetector.counts',
    'PSDC': 'linearDetector.counts',
    'DDC': 'diffractionDetector.counts',
    'TDC': 'linearDetector.counts',
    'Counts': '',
    
    # Fields defined by ice to nice translator
    'A': 'sample.latticeA',
    'B': 'sample.latticeB',
    'C': 'sample.latticeC',
    'Alpha': 'sample.latticeAlpha',
    'Beta' : 'sample.latticeBeta' ,
    'Gamma': 'sample.latticeGamma',
    'MonoMaterial': 'ei.material',
    'MonoFocus': 'mono.focus',
    }


def convert(infile, outfile=":entry"):
    """
    Load BT-7 ICE data as a nexus in-memory structure.
    """
    icedata = iceformat.read(infile)
    nicedata = bt7_ice_to_nice(icedata)
    nexus_layout = jsonutil.relaxed_load(template("bt7nxs.json"))
    #import pprint; pprint.pprint(nexus_layout)
    if not outfile:
        outfile = os.path.basename(os.path.splitext(infile)[0]) + ":entry"
    return write_nexus(outfile, nicedata, nexus_layout)    

def bt7_ice_to_nice(icedata):
    """
    Convert BT-7 ice data to NeXus.

    The instrument description is stored in bt7.xml.
    """
    # Pull together header and columns
    data = icedata.metadata.copy()
    data.update(icedata.data)
    
    # Expand lattice parameters
    data.update((k.capitalize(),v) for k,v in data['Lattice'].items())
    # Fix up monochromator selection
    if abs(data["MonoSpacing"] - 1.278) < 1e-4:
        data["MonoMaterial"] = "Cu220"
        data["MonoFocus"] = data["FocusCu"]
    else:
        data["MonoMaterial"] = "PG002"
        data["MonoFocus"] = data["FocusPG"]
        
    # Gang monochromator and analyzer blades
    data['MonoBlades'] = numpy.array([data[f] for f in iceformat.BT7_MONOCHROMATOR_BLADES])
    data['AnaBlades'] = numpy.array([data[f] for f in iceformat.BT7_ANALYZER_BLADES])

    # Gather detector data columns    
    data['SDC'] = numpy.array([icedata.data['SDC%d'%d] for d in range(3)])
    data['DDC'] = numpy.array([icedata.data['DDC%d'%d] for d in range(3)])
    data['TDC'] = numpy.array([icedata.data['TDC%02d'%d] for d in range(9)])
    if 'PSDC0' in icedata.data:
        data['PSDC'] = numpy.array([icedata.data['PSDC%02d'%d] for d in range(48)])

    # get counts on the detector
    data['Counts'] = icedata.counts()
    
    # Only include base E for FixedE.  Fixed value is already reported
    if 'FixedE' in icedata.metadata:
        data['FixedE'] = icedata.metadata['FixedE'][0]

    lattice = data['Lattice']
    data['Lattice'] = [lattice[k] for k in 'a', 'b', 'c', 'alpha', 'beta', 'gamma']
    orient = data['Orient1']
    data['Orient1'] = [orient[k] for k in 'h','k','l']
    orient = data['Orient2']
    data['Orient2'] = [orient[k] for k in 'h','k','l']
    data['FilTran'] = data['FilTran'][0]
    data['ScanVarying'] = ", ".join(data['ScanVarying'])
    data['Date'] = iso8601.format_date(data['Date'])
    data['Flip'] = data['Flip'][0]
    #data['Flip'] = [{'A':0,'B':1,'C':2,'D':3}.get(c,0)
    #                for c in data['Flip']]


    nicedata = dict((nicekey, {'value': data[icekey], 
                               'units': icedata.units(icekey), 
                               #'shortname': rename_field(nicekey),
                               })
                    for icekey,nicekey in _ICE_TO_NICE.items()
                    if icekey in data and nicekey)
    return nicedata

if __name__ == "__main__":
    main_driver(convert)
