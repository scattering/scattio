# This program is public domain
# Author: Paul Kienzle
# Initial version: William Ratcliff
"""
ICE data reader.

Usage
=====

Read in the entire file::

     import iceformat
     F = iceformat.read(path)
     print F.data
     print F.metadata

or just read in the metadata::

     import iceformat
     F = iceformat.summary(path)
     print F.metadata

The returned data object *F* has the following attributes:

    *path*

        Location of the file.

    *header*

        Contents of the file header, as text.

    *metadata*

        Set of fields, with metadata['FieldName'] giving the value for the
        field named 'FieldName'.  The data type varies from field to field, with
        numerical data converted to numbers, dates converted to struct_time
        dates, lattice converted to a dictionary, etc. Some fields have been
        renamed for consistency and clarity.

    *data*

        Set of data columns, with data['ColumnName'] giving the values.
        Numerical data has already been converted to numbers.  The remaining
        data are saved as strings.  Some columns have been renamed for
        consistency and clarity.

See the :ref:`bt7format` for a description of the *metadata* and *data*
fields.
"""
__all__ = ['ICE','read','summary','undo_camel_case','main']
import sys
import time
import re
import os

import numpy as N

from .scanparser import parse_scan

MACS_MONOCHROMATOR_BLADES = ['MonBlade%02d'%d for d in range(1,22)]
MACS_ANALYZER_BLADES = ['AnalyzerTheta%02d'%d for d in range(1,21)]
MACS_DIFF_GROUP = ['DIFF%02d'%d for d in range(1,21)]
MACS_SPEC_GROUP = ['SPEC%02d'%d for d in range(1,21)]
MACS_MONOCHROMATOR_BLADES = ['MonBlade%02d'%d for d in range(1,22)]
BT7_ANALYZER_BLADES = ['AnalyzerBlade%02d'%d for d in range(1,14)]
BT7_MONOCHROMATOR_BLADES = ['MonoBlade%02d'%d for d in range(1,11)]
TEMPERATURE_SENSORS = ['TemperatureSensor%d'%d for d in range(4)]

_ICE_UNITS = {
    'AnaSpacing': 'Ang',
    'MonoSpacing': 'Ang',
    'A1': 'degrees',
    'A2': 'degrees',
    'A3': 'degrees',
    'A4': 'degrees',
    'A5': 'degrees',
    'A6': 'degrees',
    'QX': '1/Ang',
    'QY': '1/Ang',
    'QZ': '1/Ang',
    'Ei': 'meV',
    'Ef': 'meV',
    'E': 'meV',
    'DFM': 'degrees',
    'Time': 's',
    'SmplGFRot': 'degrees',
    'SingleDet': 'degrees',
    'DiffDet': 'degrees',
    'PSDet': 'degrees',
    'FilRot': 'degrees',
    # FIXME check units on FilTrans
    'FilTilt': 'degrees',
    'FilTrans': 'mm', 
    'ApertHori': 'mm',
    'ApertVert': 'mm',
    'SmplHght': 'mm',
    'SmplWdth': 'mm',
    'BkSltHght': 'mm',
    'BkSltWdth': 'mm',
    'PreMonoCollDivergence': 'arcminutes',
    'PostAnaCollDivergence': 'arcminutes',
    'RC': 'degrees',
    'SC': 'degrees',
    'SmplElev': 'mm',
    'SmplLTilt': 'degrees',
    'SmplUTilt': 'degrees',
    'SmplLTrn': 'degrees',
    'SmplUTrn': 'degrees',
    'MagField': 'tesla',
    'Pressure': 'kPa',
    'Hsample': 'gauss',
    'Vsample': 'gauss',
    'EIcancel': 'mA',
    'EFcancel': 'mA',
    'EIguide': 'mA',
    'EFguide': 'mA',
    'EIflip': 'mA',
    'EFflip': 'mA',
    
    'FocusCu': '',
    'FocusPG': '',
    'Detector': '',
    'Monitor': '',
    'Time': 's',
    'Npoints': '',
    'Lattice': '',
    'H': '',
    'K': '',
    'L': '',
    'TemperatureHeaterPower': 'A',
    'TemperatureControlReading': '',
    'MonoTrans': 'mm',
    'MonoElev': 'mm',
    'AnalyzerRotation': 'degrees',
    'Orient1': '',
    'Orient2': '',
    
    # Provide lattice component units even though no individual keys
    'A': 'Ang',
    'B': 'Ang',
    'C': 'Ang',
    'Alpha': 'Ang',
    'Beta':  'Ang',
    'Gamma': 'Ang',
    'MonoFocus': '',
    
    # Provide units for ganged fields
    'MonoBlades': 'degrees',
    'AnaBlades': 'degrees',
    'SDC': '',
    'TDC': '',
    'DDC': '',
    'PSDC': '',
    }
_ICE_UNITS.update((f,'degrees') for f in BT7_ANALYZER_BLADES)
_ICE_UNITS.update((f,'degrees') for f in BT7_MONOCHROMATOR_BLADES)
_TEMPERATURE_FIELDS = set(['Temp', 'TemperatureSetpoint']+TEMPERATURE_SENSORS)

_RENAME_COLUMNS = {
    # Motors renamed from old to new
    'bkhght': 'BkSltHght',
    'bkwdth': 'BkSltWdth',
    'smplhght': 'SmplHght',
    'smplwdth': 'SmplWdth',
    'timestamp': 'TimeStamp',
    'FLIP': 'Flip',
    'Counts': 'Detector',
    #'MagField': 'Hsample',
    #'mfield': 'Hsample',
    #'SC': 'SollerCollimator',
    #'RC': 'RadialCollimator',
    #'DFMRot': 'MonoRot',  # drop 'DFM'; it appears to duplicate DFMRot
}

# Special field formats
_FIELD_FORMATTERS = dict(
    Path = lambda F,k: F.path,
    Date = lambda F,k: time.strftime('%Y-%m-%d %H:%M:%S', F.metadata[k]),
    Lattice = lambda F,k: '"a=%(a)g, b=%(b)g, c=%(c)g, alpha=%(alpha)g, beta=%(beta)g, gamma=%(gamma)g"'%F.metadata[k],
    Orient1 = lambda F,k: '"%(h)g, %(k)g, %(l)g"'%F.metadata[k],
    Orient2 = lambda F,k: '"%(h)g, %(k)g, %(l)g"'%F.metadata[k],
    ExperimentID = lambda F,k: F.metadata[k],
    Npoints = lambda F,k: str(F.metadata[k]),
    ScanRanges = lambda F,k: " ".join(_format_ranges(F,loose=False)),
    ScanVarying = lambda F,k: " ".join(F.metadata[k]),
    FixedE = lambda F,k: "%s=%g"%(F.metadata[k]) if k in F.metadata else ""
    )

# Fields to include by default when summarizing
_DEFAULT_FIELDS = [
    #
    'Path','Date', # metadata

    # Experiment info
    'ExperimentName', # metadata
    'ExperimentDetails','ExperimentComment', # metadata
    'ExperimentParticipants', # metadata
    'ExperimentID', # metadata

    # Scan info
    'ScanTitle','ScanComment', # metadata
    'ScanRanges','Npoints',  # metadata

    # Geometry
    'QX','QY','QZ','H','K','L',
    'E','Ei','Ef',
    'FixedE', # metadata
    'A1','A2','A3','A4','A5','A6',

    # Monitor
    'Time', 'Monitor', 'Detector',
    #'TimeStamp',  # time per individual point

    # Sample environment
    'Temp','Hsample','Vsample','MagField',

    # Sample orientation
    'Lattice','Orient1','Orient2', # metadata
    'SmplElev','SmplLTilt','SmplLTrn','SmplUTilt','SmplUTrn',

    # Polarization
    'Flip',
    'EIcancel','EIflip','EIguide',
    'EFcancel','EFflip','EFguide',

    # Aperture/Collimator
    'ApertHori','ApertVert','BkSltHght','BkSltWdth','SmplHght','SmplWdth',
    'RC','SC',
    'PreMonoColl','PostMonoColl','PreAnaColl','PostAnaColl',

    # Attenuator
    'FilRot','FilTilt','FilTran',

    # Monochromator/Analyzer
    'MonoVertiFocus','MonoHorizFocus', 'MonoDSpacing', # metadata
    'MonoElev', # Selects from available monochromators (Cu or PG for now)
    'MonoTrans',
    #'DFMRot', # Double focusing monitor rotation is just A1
    'FocusCU','FocusPG',
    'SmplGFRot',

    'AnalyzerDetectorMode', 'AnalyzerFocus', 'AnalyzerDSpacing', # metadata
    'AnalyzerRotation',

    # Detector angles
    'DiffDet','SingleDet', 'PSDet',
    ]
_DEFAULT_FIELDS += BT7_ANALYZER_BLADES
_DEFAULT_FIELDS += BT7_MONOCHROMATOR_BLADES
# TemperatureControlReading TemperatureSetpoint TemperatureHeaterPower
# TemperatureSensor0 TemperatureSensor1 TemperatureSensor2 TemperatureSensor3
#fields += ['DDC0','DDC1','DDC2']
#fields += ['SDC0','SDC1','SDC2']
#fields += ['PSD%2d'%d for d in range(0,49)]
#fields += ['TDC%2d'%d for d in range(0,8)]

class ICE(object):
    """
    ICE data format.

    f = ICE(path) sets the data location for the file but does not read
    anything.  Read the header using :meth:`summary` or read both the
    the header and the contents using :meth:`read`.

    Usually ICE is not called directly, but instead returned
    from :func:`read` or :func:`summary`.
    """
    detector_groups = ("AnalyzerDDGroup",
                       "AnalyzerDoorDetectorGroup",
                       "AnalyzerSDGroup",
                       "AnalyzerPSDGroup",
                       "DiffGroup", "SpecGroup", # MACS groups
                       )

    def __init__(self, path):
        self.path = path
        self.metadata = {}
        self.data = {}
        self.header = ""

    def summary(self):
        """
        Read the header section of the file, not the data.
        """
        file = open(self.path, 'r')
        self._readheader(file, self.path)
        file.close()
        return self

    @property
    def instrument(self):
        return "MACS" if self.metadata.get('InstrName','')=="NG0" else "BT7"

    def read(self, maxlines=N.Inf):
        """
        Read the header and data
        """
        file = open(self.path, 'r')
        self._readheader(file, self.path)
        if self.instrument == "MACS":
            self.metadata['DiffGroup'] = MACS_DIFF_GROUP
            self.metadata['SpecGroup'] = MACS_SPEC_GROUP
        self._readdata(file, maxlines=maxlines)
        file.close()
        return self

    def group(self, name):
        """
        Convert a detector group into a numpy array.
        """
        # Make sure the data has been read
        if not self.data:
            raise RuntimeError("Data for '%s' has not been read"%self.path)

        # Make sure the name is valid
        if name not in self.detector_groups:
            raise TypeError("group not in %s"%self.detector_groups)

        # Make sure the group exists and has data
        columns = self.metadata.get(name, [])
        if not columns or any(c not in self.data for c in columns):
            return N.empty((0,0),'int32')

        # Gather data columns for the group into one list
        block = [self.data[d] for d in columns]

        # Return the data as a transposed array so that points
        # are the first dimension
        return N.array(block, 'int32').T

    def format(self, field):
        """
        Return field value formatted for printing.
        """
        return _format(self, field)

    def __len__(self):
        """
        Return number of measured data points.
        """
        return len(self.data['A1'])

    def counts(self):
        """
        Return counts on the active detector as a numpy array.

        For point detectors (SD, DD), sum across the individual detectors.
        For 1-D detectors (PSD), return a 2-D array of pixel vs. point.
        For MACS, return the summed diffraction detector.

        This function uses detector position to determine counting mode so
        that diffraction mode measurements are plotted correctly even when
        the analyzer is not set to diffraction mode.

        The transmission detector counts will never be returned.
        """
        if self.instrument == "MACS":
            return N.array(self.data['DIFF'])

        DD = N.array(self.data['DiffDet'])
        if N.all(abs(DD - 180) < 1):
            group = self.metadata['AnalyzerDDGroup']
        else:
            group = self.metadata['AnalyzerDetectorDevicesOfInterest']
        counts = N.array([self.data[c] for c in group])
        if not group[0].startswith('PSD'):
            counts = N.sum(counts, axis=0)
        return counts

    def plot(self, figures=None, normalized=True):
        """
        Plot the data against the scanned variable using matplotlib.

        *figures* is a map between xaxis name and figure number.  If
        provided, all data sharing the same xaxis will be plotted in the
        same figure.  New figures will be added as necessary.
        """
        import pylab

        if figures is None: figures = {}
        label = "%s%s: %s"%(self.metadata['Filename'],
                            "".join(set(self.data.get('Flip',[]))),
                            self.metadata['ScanTitle'],
                            )
        xaxis = self.metadata['ScanVarying'][0]
        x = N.array(self.data[xaxis])
        counts = self.counts()
        norm = N.array(self.data['Monitor'])+1 if normalized else 1
        if len(counts.shape) == 2:
            # Should decide whether PSD is operating in x coordinates
            # (e.g., measuring multiple Q simultaneously during a Q scan)
            # or as an independent axis.  For now, assume the latter.
            y = N.arange(1,counts.shape[0]+1)
            H = pylab.figure()
            H.canvas.set_window_title(self.metadata['Filename'])
            pylab.pcolormesh(x,y,N.log((counts+1)/norm))
            pylab.xlabel(xaxis)
            pylab.ylabel('pixels')
            pylab.title(self.metadata['Filename'])
        elif not N.any(N.isnan(x)):
            if xaxis in figures:
                pylab.figure(figures[xaxis])
            else:
                H = pylab.figure()
                H.canvas.set_window_title(xaxis)
                figures[xaxis] = H.number
            pylab.semilogy(x,(counts+1)/norm,'-*',label=label)
            H = pylab.legend(mode='expand')
            try: H.draggable(True)
            except: pass
            pylab.xlabel(xaxis)
            yaxis = 'counts/monitor' if normalized else 'counts'
            pylab.ylabel(yaxis)

    def add_column(self, name, value):
        """
        Add a column to the data
        """
        if name in self.metadata['Columns']:
            raise KeyError("%r already in data"%name)
        self.metadata['Columns'].append(name)
        self.data[name] = value
    def del_column(self, name):
        """
        Remove a column from the data
        """
        if name not in self.metadata['Columns']:
            raise KeyError("%r not in data"%name)
        self.metadata['Columns'].remove(name)
        del self.data[name]

    def rename_column(self, name, newname):
        if name in self.metadata['Columns']:
            self.add_column(newname, self.data[name])
            self.del_column(name)

    def units(self, column):
        if column in _TEMPERATURE_FIELDS:
            return self.metadata['TemperatureUnits']
        else:
            return _ICE_UNITS.get(column,None)

    def _readheader(self, file, path):
        """
        Read the data headers.
        """
        header = []
        metadata = {}
        count = 0
        while True:  # Repeat until #Columns is read
            count += 1
            line = file.readline()
            header.append(line)
            key,value = _parse_keyval(line)
            target = key # Could rename the metadata fields if we wanted
            if key == "Date":
                #Date YYYY-MM-DD HH:MM:SS EST/EDT
                isdst = value.endswith(" EDT")
                T = time.strptime(value[:-4], "%Y-%m-%d %H:%M:%S")
                T = (T.tm_year, T.tm_mon, T.tm_mday,
                     T.tm_hour, T.tm_min, T.tm_sec,
                     T.tm_wday, T.tm_yday, isdst)
                metadata[target] = time.struct_time(T)
            elif key in ("Ncolumns", "Npoints"):
                #Key int
                metadata[target] = int(value)
            elif key in ("Epoch",
                         "MonoSpacing",
                         "AnaSpacing"):
                #Key float
                metadata[target]=float(value)
            elif key == "Orient":
                #Orient h1 k1 l1 h2 k2 l2
                field = 'h','k','l'
                value = [float(vi) for vi in value.split()]
                metadata['Orient1'] = dict(zip(field,value[:3]))
                metadata['Orient2'] = dict(zip(field,value[3:]))
            elif key == "Lattice":
                #Lattice a b c alpha beta gamma
                field = 'a','b','c','alpha','beta','gamma'
                value = [float(vi) for vi in value.split()]
                metadata[target] = dict(zip(field,value))
            elif key == "AnalyzerDetectorMode":
                #Key mode# mode_name
                num,name = value.split()
                metadata[target] = name
            elif key in ("Reference",
                         "Signal",
                         "Scan"):
                #Key column# column_name
                num,name = value.split()
                metadata[target] = name
            elif target in self.detector_groups:
                #Key column column ...
                metadata[target] = value.split()
            elif key == "AnalyzerDetectorDevicesOfInterest":
                #Key column column ...
                metadata[target] = value.split()
            elif key == "Fixed":
                #Fixed column column ... | #Fixed All devices are free
                if value.startswith('All '):
                    metadata[target] = []
                else:
                    metadata[target] = value.split()

            elif key=="FixedE":
                #FixedE Ef|Ei value
                try:
                    name,num = value.split()
                    metadata[target] = name,float(num)
                except ValueError:
                    pass
            elif key=="ScanRanges":
                #ScanRanges column# column_name column# column_name ...
                # Suppressed.  Pull scan ranges from ScanDescr instead.
                pass
            elif key=="ScanDescr":
                #ScanDescr scan description string
                metadata[target] = value
                scan = parse_scan(value)
                metadata['ScanVarying'] = scan.varying
                metadata['ScanDetector'] = scan.detector
                metadata['ScanRanges'] = scan.oranges
                metadata['ScanLimits'] = scan.ranges
                metadata['ScanTitle'] = scan.scan_description.get('Title','')
                metadata['ScanComment'] = scan.scan_description.get('Comment','')
            elif key=='UBEnabled':
                # Boolean
                metadata[target] = (value!='0')
            elif key=='Columns':
                #Key column column ...
                # split the value into individual names, then lookup
                # replacement names in the _RENAME_COLUMNS dictionary,
                # defaulting to the existing column name if there is
                # no replacement.
                names = [_RENAME_COLUMNS.get(c,c) for c in value.split()]
                metadata[target] = names

                # done with header
                break
            else:
                # Store everything else without conversion
                metadata[target] = value


        # repair missing file names
        if metadata['Filename'] is None:
            metadata['Filename'] = os.path.splitext(os.path.basename(path))[0]

        # Guess sequence number from filename
        pattern = re.compile('^(?P<base>[^.]*?)(?P<seq>[0-9]*)(?P<ext>[.].*)?$')
        match = pattern.match(metadata['Filename'])
        metadata['ScanBasename'] = match.group('base')
        metadata['ScanID'] = match.group('seq')

        self.metadata = metadata

        self.header = "\n".join(header)

    def _readdata(self, file, maxlines):
        """
        Read the data columns, converting those that we can into numbers.
        """
        data = [[] for _ in self.metadata['Columns']]
        count = 0
        while True:
            line = file.readline()
            if line == '':
                break
            if line.startswith("#"):
                continue
            values = line.strip().split()
            for i,v in enumerate(line.strip().split()):
                try:
                    data[i].append(float(v))
                except ValueError:
                    if v == 'N/A':
                        data[i].append(N.NaN)
                    else:
                        data[i].append(v)
                except IndexError:
                    print >>sys.stderr,"Line too long in",self.path
                    break
            count += 1
            if count >= maxlines:
                break

        self.data = dict(zip(self.metadata['Columns'],data))
        self._fix_timestamp()
        self._guess_monochromator_collimator()
        self._guess_analyzer_collimator()
        self._fix_varying()
        self._fix_EiEf()

        #self._generate_collimator_deltas()
        #self._generate_flipper_current_ratios()

    def _guess_monochromator_collimator(self):
        
        try:
            # Fails if PreMonoColl is not defined or if there is no data
            collstr = self.data['PreMonoColl'][0]
        except:
            return
        
        if collstr.endswith("MIN"):
            collimator = "SOLLER",int(collstr[:-3])
        elif collstr in ("OPEN","OPEN_"):
            collimator = "OPEN",0
        else:
            raise ValueError("unexpected collimator value "%collstr)
            
            
        self.metadata['PreMonoCollType'],self.metadata['PreMonoCollDivergence'] = collimator


    def _guess_analyzer_collimator(self):
        """
        Attempt to guess analyzer collimator from instrument state.

        Not sure if the position mapping to collimator is correct.
        """

        # Can't do anything if we have no data
        if len(self.data.get('SingleDet',[])) == 0: 
            return

            
        try:
            # Fails if required fields are not defined or if there is no data
            group = self.metadata['AnalyzerDetectorDevicesOfInterest']
            DD = float(self.data['DiffDet'][0])
            SD = float(self.data['SingleDet'][0])
            PSD = float(self.data['PSDet'][0])
            A6 = SD if group[0].startswith('SDC') else PSD
            dRC = A6 - float(self.data['RC'][0])
            dSC = A6 - float(self.data['SC'][0])
        except:
            return

        # Check for diffraction mode, RC, SC 1-3 or OPEN.
        if abs(DD - 180) < 1:
            collimator = 'OPEN',0
        elif abs(dRC) < 3:
            collimator = 'RADIAL',60
        elif abs(dSC) < 3:
            collimator = 'SOLLER',25
        elif abs(dSC - 45) < 3:
            collimator = 'SOLLER',50
        elif abs(dSC - 67) < 3:
            collimator = 'SOLLER',120
        else:
            collimator = 'OPEN',0

        # Create a new field with what we've found.
        self.metadata['PostAnaCollType'],self.metadata['PostAnaCollDivergence'] = collimator

    def _generate_collimator_deltas(self):
        """
        Generate data columns for collimator position relative to
        detector positions.

        This is useful to help understand how collimator position
        is generated, but will not be useful in production code.
        """
        try:
            for k in 'A6','SingleDet','PSDet','DiffDet','SC','RC':
                self.data[k] = N.array(self.data[k])
            self.data['SC-SD'] = self.data['SC']-self.data['SingleDet']
            self.data['SC-PSD'] = self.data['SC']-self.data['PSDet']
            self.data['SC-DD'] = self.data['SC']-self.data['DiffDet']
            self.data['RC-SD'] = self.data['RC']-self.data['SingleDet']
            self.data['RC-PSD'] = self.data['RC']-self.data['PSDet']
            self.data['RC-DD'] = self.data['RC']-self.data['DiffDet']
            self.metadata['Columns'].extend(('SC-SD','SC-PSD','SC-DD'))
            self.metadata['Columns'].extend(('RC-SD','RC-PSD','RC-DD'))
        except KeyboardInterrupt:
            raise
        except:
            pass
    def _generate_flipper_current_ratios(self):
        """
        Generate data columns for EiFlipRatio and EfFlipRatio
        equal to Ei/sqrt(EIflip) and Ef/sqrt(EFflip) respectively.

        This is useful to help understand the relationship between
        flipper current and energy.
        """
        if 'Ei' in self.data and 'EIflip' in self.data:
            self.data['EiFlipRatio'] = N.array(self.data['EIflip'])/N.sqrt(N.array(self.data['Ei']))
            self.metadata['Columns'].extend('EiFlipRatio')
        if 'Ef' in self.data and 'EFflip' in self.data:
            self.data['EfFlipRatio'] = N.array(self.data['EFflip'])/N.sqrt(N.array(self.data['Ef']))
            self.metadata['Columns'].extend('EfFlipRatio')

    def _fix_EiEf(self):
        """
        Create Ei/Ef columns if they are missing.
        """
        # TODO: can compute Ei from A1-A2 and Ef from A5-A6
        if 'E' in self.data and 'FixedE' in self.metadata:
            delta = N.array(self.data['E'])
            base,value = self.metadata['FixedE']
            if not 'Ef' in self.data:
                if base == 'Ef':
                    self.data['Ef'] = N.ones_like(delta)*value
                else:
                    self.data['Ef'] = delta+value
            if not 'Ei' in self.data:
                if base == 'Ei':
                    self.data['Ei'] = N.ones_like(delta)*value
                else:
                    self.data['Ei'] = delta+value

    def _fix_timestamp(self):
        """
        If there is no timestamp on the data, create one
        """
        if 'TimeStamp' not in self.data:
            epoch = self.metadata['Epoch']
            point_times = self.data['Time']
            timestamp = N.cumsum([epoch]+point_times[:-1])
            self.metadata['Columns'].append('TimeStamp')
            self.data['TimeStamp'] = timestamp

    def _fix_varying(self):
        """
        If the varying field is given in lowercase but the data column is
        recorded in uppercase, perform the translation.
        """
        self.metadata['ScanVarying'] = [self._fix_one_varying(c)
                                        for c in self.metadata['ScanVarying']]
        self.metadata['ScanRanges'] = dict((self._fix_one_varying(c),v)
                                           for c,v in self.metadata['ScanRanges'].items())

    def _fix_one_varying(self, column):
        # Usually the name is right
        if column in self.data: return column
        # Check if it is a lowercase version of a column that is going
        # to be renamed
        lc = column.lower()
        for k in _RENAME_COLUMNS.keys():
            if lc == k.lower(): return _RENAME_COLUMNS[k]
        # Check if it is a lowercase version of an existing column
        for k in self.data.keys():
            if lc == k.lower(): return k
        # Individual hacks
        if column == "CollSoller": return "SC"
        if column == "DFMaxis": return "DFM"
        # Column does not exist.  We could raise an error here, but that's
        # just annoying if the user doesn't care about ScanVarying, so
        # simply return the original column.
        return column




def _parse_keyval(line):
    """
    Split '#key value' into key,value pair.
    """
    pos = line.find(' ')
    if pos > -1:
        key = line[1:pos]
        val = line[pos:-1].strip()
    else:
        key = line[1:].strip()
        val = ''
    return key,val


# http://stackoverflow.com/questions/1175208/does-the-python-standard-library-have-function-to-convert-camelcase-to-camel-case/1176023#1176023
def undo_camel_case(names):
    """
    Convert a list of names from camel case to underscore form.
    """
    first_cap = re.compile('(.)([A-Z][a-z]+)')
    all_cap = re.compile('([a-z0-9])([A-Z])')
    return [all_cap.sub(r'\1_\2', first_cap.sum(r'\1\2', si)).lower()
            for si in names]

def summary(path):
    """
    Open the fiile and read the data header.
    """
    return ICE(path).summary()
def read(path):
    """
    Open and read the file.
    """
    return ICE(path).read()

# ============================================
# Test, demo, driver code
def test():
    """
    Read a file and check the contents.
    """
    from .utils import example
    F = read(example('bt7','201102-16363-largeq_90397.bt7'))
    assert abs(F.data['A2'][-1] - 23.2682) < 1e-5
    assert F.metadata['ScanVarying'][0] == 'E'

def demo():
    """
    Read and dump the contents of an example file.
    """
    from .utils import example
    _dump([example('bt7','201102-16363-largeq_90397.bt7')])

def _dump(files):
    for f in files:
        F = ICE(f).read()
        print "====== %s ========="%f
        for d in F.detector_groups:
            print d,"x".join(str(dim) for dim in F.group(d).shape)
        for k in sorted(F.data.keys()):
            print k,_scalar_or_list(F.data[k])
        for k in sorted(F.metadata.keys()):
            print k,F.metadata[k]



def _show_fields(files):
    for f in files:
        try:
            F = ICE(f).summary()
        except:
            import traceback, sys
            print >>sys.stderr, "===== %s ====="%f
            print >>sys.stderr, traceback.format_exc()
            continue
        print " ".join(sorted(F.metadata.keys()))

def _show_scan(files):
    for f in files:
        try:
            F = ICE(f).read()
        except:
            import traceback, sys
            print >>sys.stderr, "===== %s ====="%f
            print >>sys.stderr, traceback.format_exc()
            continue
        keys = {}
        if F.metadata['Filename'].startswith('fpx'):
            keys['op'] = '    bt7.findpeak'
        else:
            keys['op'] = '    bt7.scan'
        keys['id'] = F.metadata['ScanID']
        keys['n'] = F.metadata['Npoints']
        keys['ref'] = F.metadata['Reference']
        refcol = F.data[F.metadata['Reference']]
        keys['val'] = refcol[0] if len(refcol)>0 else 0
        keys['cr'] = '\n'+' '*(len(keys['op'])+1)
        keys['fields'] = ', '.join(_format_ranges(F, loose=False))
        keys['title'] = F.metadata['ScanTitle']

        if 'findpeak' in keys['op']:
            print "%(op)s(id=%(id)s, %(ref)s=%(val)g, Npoints=%(n)d, %(fields)s)"%keys
        else:
            print "%(op)s(id=%(id)s, %(ref)s=%(val)g, Npoints=%(n)d, ScanTitle='%(title)s',%(cr)s%(fields)s)"%keys

def _tabulate(files, fields=_DEFAULT_FIELDS):
    print ",".join(fields)
    for f in files:
        try:
            F = ICE(f).read()
        except:
            import traceback, sys
            print >>sys.stderr, "===== %s ====="%f
            print >>sys.stderr, traceback.format_exc()
            continue
        print ",".join(_format(F,c) for c in fields)

def _format(file,field):
    """
    Format metadata for printing
    """
    formatter = _FIELD_FORMATTERS.get(field,None)
    if formatter:
        # Specialized formatter
        return formatter(file,field)
    elif field in file.metadata:
        # Generic metadata
        v = str(file.metadata[field]).replace('\n',r'\n').replace('"','""')
        return '"%s"'%v
    elif field in file.data and file.data[field] != []:
        # Generic data
        return _compact_range(file.data[field])
    else:
        # Missing data
        return ''

def _format_ranges(F, loose=True):
    ranges = ["%s = %s"%(n,_format_one_range(F.metadata['ScanRanges'][n]))
              for n in F.metadata['ScanVarying']]
    if not loose:
        ranges=[r.replace(' ','') for r in ranges]
    return ranges

def _format_one_range(range):
    if 'center' in range:
        return "(%g,%g)"%(range['center'], range['step'])
    elif 'stop' in range:
        return "(%g,%g,'s')"%(range['start'], range['stop'])
    elif 'step' in range:
        return "(%g,%g,'i')"%(range['start'], range['step'])

def _compact_range(vector, exclude_nan=True):
    """
    Return a constant, a range or a list of choices, whichever is the most
    appropriate representation of a set of data.
    """
    if exclude_nan:
        vector = [v for v in vector if v != "N/A"]
    if vector == []:
        return ""

    # Check if the set is numeric, treating it as a set of strings if not
    try:
        vector = N.asarray(vector,'d')
    except ValueError:
        # Default: return enumerated choice list
        return "|".join(sorted(set(str(v) for v in vector)))

    # We are here, so we are numeric
    low,high = N.min(vector),N.max(vector)
    if high==low or (high-low)/(abs(high)+abs(low)) < 0.01:
        return "%g"%vector[0]
    else:
        return "%g : %g"%(low,high)

def _scalar_or_list(vector, exclude_nan=True):
    """
    Return a constant, a range or a list of choices, whichever is the most
    appropriate representation of a set of data.
    """
    if exclude_nan:
        vector = [v for v in vector if not isinstance(v,str) and not N.isnan(v)]
    if vector == []:
        return ""

    # Check if the set is numeric, treating it as a set of strings if not
    try:
        vector = N.asarray(vector,'d')
    except ValueError:
        if len(set(str(v) for v in vector)) == 1:
            return str(vector[0])
        else:
            return " ".join(str(v) for v in vector)

    # We are here, so we are numeric
    low,high = N.min(vector),N.max(vector)
    if high == low or (high-low)/(abs(high)+abs(low)) < 0.01:
        return "%g"%vector[0]
    else:
        return " ".join("%g"%v for v in vector)

def _plot(files, normalized):
    import pylab
    figures = {}
    for f in files:
        try: F = ICE(f).read()
        except: raise
        if len(F) == 0: continue
        F.plot(figures, normalized=normalized)
    pylab.show()


def main():
    """
    Command line driver.

    Usage::

       python -m nice.reader.iceformat options files*

    The options are one and only one of the following:

      ======================= ===========================================
      <empty>                 Show the data, one field per line
      -t                      Produce a csv table with the default fields
      -T field:field:...      Produce a table with the given fields
      -f                      Show header fields available
      -p                      Plot raw data
      -P                      Plot data normalized by monitor
      -s                      Show scan description
      ======================= ===========================================
    """
    import sys
    if sys.argv[1] == '-t':
        _tabulate(sys.argv[2:])
    elif sys.argv[1] == '-T':
        fieldlist = sys.argv[2].split(':')
        _tabulate(sys.argv[3:], fields=fieldlist)
    elif sys.argv[1] == '-f':
        _show_fields(sys.argv[2:])
    elif sys.argv[1] == '-p':
        _plot(sys.argv[2:], normalized=True)
    elif sys.argv[1] == '-P':
        _plot(sys.argv[2:], normalized=False)
    elif sys.argv[1] == '-s':
        # python -m reader.iceformat -T Date:Path 15693/*.bt7  | sort | sed -es/^.*,// | xargs python -m reader.iceformat -s > scan.txt
        _show_scan(sys.argv[2:])
    else:
        _dump(sys.argv[1:])

if __name__=='__main__':
    #demo()
    #test()
    main()
