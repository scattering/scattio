import os
import time

import numpy

#==== Example file =====
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
    def __init__(self, filename):
        with open(filename, 'rt') as file:
            self.path = filename
            self._read_file(file)

    def _read_file(self, file):
        self._read_parameters(file)
        self._read_motors(file)
        self._read_blades(file)
        self._read_data(file)
    
    def _read_parameters(self, file):
        lines = [file.readline() for _ in range(5)]
        #print "lines[0]",lines[0],lines[0].split("'")
        _, filename, _, date, bits, base, pts, type, _ = lines[0].split("'") 
        self.filename = filename
        self.date = time.strptime(date, '%b %d %Y')
        bits = bits.split()
        self.experiment_parameters = [int(s) for s in bits[:6]]
        self.monitor = float(bits[6])
        self.prefactor = int(bits[7])
        self.base = base
        self.pts = int(pts)
        self.type = type
        self.comment = lines[2].strip()
        bits = lines[3].split()
        self.collimation = [int(s) for s in bits[:3]]
        self.mosaic = [int(s) for s in bits[3:7]]
        self.wavelength = float(bits[7])
        self.Tstart = float(bits[8])
        self.Tincr = float(bits[9])
        self.Hfield = float(bits[10])
        self.numdetectors = int(bits[11])

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
        # Get column names from
        #     $ M4=     11.000  T= 250.770 C=   0.81 N=           0
        self.column_names = [s.split()[-1] for s in line.split('=')[:-1]]
        self.column_number = dict((c,i) for i,c in enumerate(self.column_names))
        # Final data block is "$ timestamp"
        while '=' in line:
            fields = [s.split()[0] for s in line.split('=')[1:]]
            columns.append([float(s) for s in fields])
            line = file.readline()
            monitors.append([int(s) for s in line[1:].split()])
            line = file.readline()
            parts = []
            while line.startswith(' '):
                parts.append(line)
                line = file.readline()
            joined_line = "".join(s.strip() for s in parts)
            detectors.append([int(s) for s in joined_line.split(',')])
            
            while line.startswith('$ Stat Fail:') or line.startswith('$ Main_Stat Fail:'):
                # silently skip?
                line = file.readline()
            
        try:
            self.timestamp = time.strptime(line[2:22], '%d-%b-%Y %H:%M:%S')
        except:
            self.timestamp = self.date
            line = line.strip()
            if line != '':
                print "could not parse timestamp %r in %r"%(line.strip(),self.path)
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
            start,step,stop = [float(s) for s in words[1:]]
            motors.append((name,start,step,stop))
        self.motors = motors

def monavg(plot=False):
    import sys
    import pylab
    import datetime
    
    files = sys.argv[1:]
    summary = {}
    for f in files:
        try:
            data = ICPBT1(f)
        except:
            if not os.path.basename(f).startswith('fpx'): print "skipping",f
            continue
        if data.base != 'NEUT':
            print >>sys.stderr, "by time",f
        elif 'C' not in data.column_number:
            print >>sys.stderr, "missing count time",f
        else:
            times = data.columns[:,data.column_number['C']]
            u,s = numpy.mean(times),numpy.std(times)
            #print data.path,times
            if s/u > 0.02 and (u > 1 or s > 0.1):
                print >>sys.stderr, "high count time variation (%10.3f +/- %10.3f) in %r"%(u,s,data.path)
            monitors = data.monitor*data.prefactor*len(times)
            seconds = sum(times)*60
            collimation = "-".join("%d"%c for c in data.collimation)
            points = summary.setdefault((collimation,data.wavelength),[])
            points.append((data.timestamp,monitors/seconds,data.path))
    
    for k,v in sorted(summary.items()):
        if plot:
            if len(v) < 10: continue
            coll,wavelen = k
            dates,rates,paths = zip(*v)
            dates = [datetime.datetime.fromtimestamp(time.mktime(s)) for s in dates]
            pylab.plot(pylab.date2num(dates),rates, 'o',
                       label=coll+" %.3f"%wavelen,
                       hold=True)
        else:
            print "== %s %.3f =="%k
            for date,rate,path in v:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S",date)
                print stamp,"%10.3f"%rate,path
                
    if plot:
        pylab.grid(True)
        ax = pylab.gca()
        ax.xaxis_date()
        ax.xaxis.set_major_locator(pylab.MonthLocator(interval=3))
        ax.xaxis.set_minor_locator(pylab.WeekdayLocator(pylab.MO))
        ax.xaxis.set_major_formatter(pylab.DateFormatter("%b '%y"))
        pylab.legend()
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
