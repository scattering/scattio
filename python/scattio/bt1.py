import os
import time

import numpy

#==== fpx file ====
# Motor no.  4    Intensity at Detector:    1Dec 10 2010 16:17
#    0.9990          5684
#    ...


#==== ICP file =====
#'srnaf002.bt1' 'Dec 18 2012' 1   0   0   0 1 1  142284.    1  'NEUT'  201  'RAW'
#  Filename         Date       Exp. Parameters     Mon     Prf  Base   #pts  Type
#srnaf Sr1.25Na1.5Fe5O2(PO4)5 3.5g Ge311/60/ 150K
#  60   20    7    0   0   0   0   2.0780     0.00000 0.00000   0.00000   32
# Collimation      Mosaic    Wavelength   T-Start   Incr.   H-field #Det
#  3      0.0000   0.0000   0.0000
#  4      1.3000   0.0500  11.3000
# Mot:    Start       Step      End
#  2.850  2.617  2.863  2.408  2.295  2.369  2.024  1.699  1.610  1.331  1.241
#  1.214  1.068  1.000  1.084  0.983  0.959  1.004  1.097  1.030  0.951  1.013
#  0.926  1.162  1.000  1.005  0.950  0.988  0.986  0.970  0.989  0.980
# Detector Relative Scalefactors     GE311
#   0.00   1.00   1.29  -0.48   1.53  -0.98   2.03   0.89   1.54   1.28   0.40
#   0.35   1.53  -1.57   0.63   1.43  -0.08  -0.01  -0.78   0.16  -1.08  -2.08
#  -1.23  -0.47   0.43  -0.27  -2.60   0.88  -1.34   2.24   3.00   4.00
# Detector Relative Zero Angles      GE311
# Data in 'N' Detector Blocks with N = #scl
# $ M4=     11.250  T= 250.790 C=   0.81 N=           0
# $                0               0               0              52
#   52,53,36,59,48,47,544,98,75,106,162,133,166,119,199,109,284,359,134,178,227,
#   338,231,150,194,169,138,188,178,214,418,559
#      .
#      .
#      .
# $ M4=     11.300  T= 250.740 C=   0.81 N=           0
# $                0               0               0              50
#  50,50,42,43,53,46,495,74,72,109,117,107,155,126,180,118,302,409,129,177,230,
#  339,228,159,176,182,159,184,165,208,453,547
# $ 18-Dec-2012 16:11:22


class ICPBT1(object):
    MONOCHROMATORS = dict([
        ('Ge(311)', 2.079),
        ('Cu(311)', 1.540),
        ('Ge(733)', 1.197),
        ])
    def __init__(self, filename):
        basename = os.path.basename(filename)
        if os.path.getsize(filename) == 0:
            raise ValueError('empty file')

        with open(filename, 'rt') as file:
            self.path = filename
            self._read_file(file)

    def _read_file(self, file):
        self._read_parameters(file)
        self._read_motors(file)
        self._read_blades(file)
        self._read_data(file)

    def _read_parameters(self, file):
        line0 = file.readline()
        if line0.startswith(' Motor'): raise IOError("findpeak files not supported")
        if "Start of Run" in line0: raise IOError("monrec files not supported")

        _, filename, _, date, bits, base, pts, type, _ = line0.split("'")
        self.filename = filename
        try:
            self.date = time.strptime(date, '%b %d %Y')
        except ValueError:
            self.date = time.strptime(date, '%d-%b-%Y')
        bits = bits.split()
        self.experiment_parameters = [int(s) for s in bits[:6]]
        self.monitor = float(bits[6])
        self.prefactor = int(bits[7])
        self.base = base
        self.pts = int(pts)
        self.type = type

        _,line2,line3,_ = [file.readline() for _ in range(4)]

        self.comment = line2.strip()
        bits = line3.split()
        self.collimation = [int(s) for s in bits[:3]]
        self.mosaic = [int(s) for s in bits[3:7]]
        self.recorded_wavelength = float(bits[7])
        for k,v in self.MONOCHROMATORS.items():
            if abs(self.recorded_wavelength - v) < 0.1:
                self.wavelength = v
                self.monochromator = k
                break
        else:
            self.wavelength = self.recorded_wavelength
            self.monochromator = 'unknown'

        self.Tstart = float(bits[8])
        self.Tincr = float(bits[9])
        self.Hfield = float(bits[10])
        # Jan '04 files were missing number of detectors
        try:
            self.numdetectors = int(bits[11])
        except IndexError:
            self.numdetectors = 32

    def _read_blades(self, file):
        lines = [file.readline() for _ in range(8)]
        monochromator = lines[3].split()[-1]
        scale = lines[0].split() + lines[1].split() + lines[2].split()
        angle = lines[4].split() + lines[5].split() + lines[6].split()
        self.scale = [float(s) for s in scale]
        self.angle = [float(s) for s in angle]
        file.readline() # comment about data in 'N' detector blocks

    def _read_data(self, file):
        detectors = []
        columns = []
        monitors = []
        line = file.readline()

        if line.startswith('$Rocking'):
            line = file.readline()


        # Get column names from
        #     $ M4=     11.000  T= 250.770 C=   0.81 N=           0
        self.column_names = [s.split()[-1] for s in line.split('=')[:-1]]
        self.column_number = dict((c,i) for i,c in enumerate(self.column_names))
        # $Rocking motor  3 between  -10.00 and   10.0
        # Final data block is "$ timestamp"
        while '=' in line:
            fields = [s.split()[0] for s in line.split('=')[1:]]
            columns.append([float(s) for s in fields])
            line = file.readline()
            if line.startswith('$'):
                monitors.append([int(s) for s in line[1:].split()])
                line = file.readline()
            parts = []
            while line.startswith(' '):
                parts.append(line)
                line = file.readline()
            joined_line = "".join(s.strip() for s in parts)
            if joined_line.endswith(','): joined_line = joined_line[:-1]
            detectors.append([int(s) for s in joined_line.split(',')])

            while 'ail:' in line:
                # silently skip?
                line = file.readline()
        self.timestamp = self.date # Default timestamp to date at start of file
        if line.startswith('$'):
            try:
                self.timestamp = time.strptime(line[2:22], '%d-%b-%Y %H:%M:%S')
            except:
                line = line.strip()
                if line != '':
                    print >>sys.stderr,"could not parse timestamp %r in %r"%(line.strip(),self.path)
        self.counts = numpy.array(detectors)
        self.monitors = numpy.array(monitors)
        self.columns = numpy.array(columns)

    def _read_motors(self, file):
        motors = []
        while True:  # read until 'Mot:' line
            line = file.readline()
            words=line.split()
            if words[0] == 'Mot:': break
            name = words[0] if not words[0].isdigit() else 'M'+words[0]
            try:
                start,step,stop = [float(s) for s in words[1:]]
            except:
                # fortran uses fixed width fields, which may run into each other
                # if the simple parse doesn't work, try the known field widths.
                start,step,stop = float(line[6:15]),float(line[15:24]),float(line[24:33])
            motors.append((name,start,step,stop))
        self.motors = motors

def monavg(plot=False):
    import sys
    import pylab
    import matplotlib
    import datetime

    files = sys.argv[1:]
    summary = {}
    count = 0
    for f in files:
        try:
            data = ICPBT1(f)
        except Exception,exc:
            #import traceback
            #traceback.print_exc()
            if 'files not supported' in exc.message or 'empty' in exc.message:
                pass
            else:
                raise
                print >>sys.stderr,"error",exc.message,f
            continue
        if data.base != 'NEUT':
            #print >>sys.stderr, "by time",f
            pass
        elif 'C' not in data.column_number:
            #print data.columns_names
            print >>sys.stderr, "missing count time",f
        else:
            times = data.columns[:,data.column_number['C']]
            u,s = numpy.mean(times),numpy.std(times)
            #print data.path,times
            if s/u > 0.02 and (u > 1 or s > 0.1):
                #print >>sys.stderr, "high count time variation %d%% (%10.3f +/- %10.3f) in %r"%(int(100*s/u),u,s,data.path)
                pass
            monitors = data.monitor*data.prefactor*len(times)
            seconds = sum(times)*60
            key = "%s %2d'"%(data.monochromator,data.collimation[0])
            points = summary.setdefault(key,[])
            points.append((data.timestamp,monitors/seconds,data.path))
            count += 1

    if False and len(summary) > 7:
        items = list(sorted((len(v),k) for k,v in summary.items()))
        _,saved_keys = zip(*items[-7:])
        summary = dict([(k,summary[k]) for k in saved_keys])

    plot = plot and not count < 5
    for i,(k,v) in enumerate(sorted(summary.items())):
        if plot:
            #if len(v) < 10: continue
            dates,rates,paths = zip(*v)
            dates = [datetime.datetime.fromtimestamp(time.mktime(s)) for s in dates]
            h = pylab.plot(pylab.date2num(dates),rates, 'o' if i<7 else '^', label=k, hold=True)
            #print "add hline",h[0].get_color(), pylab.median(rates)
            pylab.axhline(pylab.median(rates), color=h[0].get_color(), linestyle=':', hold=True)
        else:
            print "== %s =="%k
            for date,rate,path in v:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S",date)
                print stamp,"%10.3f"%rate,path

    if plot:
        pylab.grid(which='y')
        ax = pylab.gca()
        days = ax.dataLim.xmax - ax.dataLim.xmin
        #print "days",days, ax.dataLim.xmin, ax.dataLim.xmax
        if days > 5*365:
             major = pylab.YearLocator(interval=1)
             minor = pylab.MonthLocator(interval=6)
             label = pylab.DateFormatter("'%y")
        elif days > 2*365:
             major = pylab.MonthLocator(interval=6)
             minor = pylab.MonthLocator(interval=3)
             label = pylab.DateFormatter("%b '%y")
        elif days > 365:
             major = pylab.MonthLocator(interval=3)
             minor = pylab.MonthLocator(interval=1)
             label = pylab.DateFormatter("%b '%y")
        elif days > 365/2:
             major = pylab.MonthLocator(interval=2)
             minor = pylab.MonthLocator(interval=1,bymonthday=(1,15))
             label = pylab.DateFormatter("%b '%y")
        elif days > 365/6:
             major = pylab.MonthLocator(interval=1)
             minor = pylab.MonthLocator(interval=1,bymonthday=(1,15))
             label = pylab.DateFormatter("%b '%y")
        elif days > 15:
             major = pylab.MonthLocator(interval=1,bymonthday=(1,10,20))
             minor = pylab.DayLocator(interval=1)
             label = pylab.DateFormatter("%b %d")
        elif days > 5:
             major = pylab.DayLocator(interval=5)
             minor = pylab.DayLocator(interval=1)
             label = pylab.DateFormatter("%b %d")
        else:
             major = pylab.DayLocator(interval=1)
             minor = pylab.DayLocator(interval=1)
             label = pylab.DateFormatter("%b %d")
        ax.xaxis.set_major_locator(major)
        ax.xaxis.set_minor_locator(minor)
        ax.xaxis.set_major_formatter(label)
        #ax.xaxis_date()
        pylab.title('Monitor rate on BT-1', fontsize=28)
        pylab.xlabel('Time', fontsize=20)
        pylab.ylabel('Monitor Rate (counts/second)', fontsize=20)
        legend = pylab.legend(loc='best', fancybox=True, numpoints=1)
        legend.get_frame().set_alpha(0.7)
        matplotlib.rc('font', size=14)
        pylab.show()

def demo():
    import sys
    from pprint import pprint

    for f in sys.argv[1:]:
        data = ICPBT1(f)
        pprint(data.__dict__)

if __name__ == "__main__":
    #demo()
    monavg(plot=True)
