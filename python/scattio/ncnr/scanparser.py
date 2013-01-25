# This program is in the public domain
# Author: William Ratcliff
"""
Parser for ICE scan strings
"""
VARYING_THRESHOLD=1e-6


simple_scans_parameter=['Title','Type','Ef', 'Ei','FixedE','Counts','CountType','DetectorType','Prefac','Npts','Timeout','HoldPoint','HoldScan','Comment',
                        'Filename']
aliased_scan_parameter=['w_i','w_c','w_f','w_s',
                        'h_i','h_c','h_f','h_s',
                        'k_i','k_c','k_f','k_s',
                        'l_i','l_c','l_f','l_s']

#energy_alias=['w_i','w_c','w_f','w_s']
w_alias=['w_i','w_c','w_f','w_s']
h_alias=['h_i','h_c','h_f','h_s']
k_alias=['k_i','k_c','k_f','k_s']
l_alias=['l_i','l_c','l_f','l_s']
ignore_list=['RangeStrings','ScanString']


def parse_scan(s):
    scan = Scan()
    scan.parse_scan(s)
    return scan

class Scan(object):
    def __init__(self):
        self.scan_description = {}

    def parse_scan(self, scanstr):
        scanstr=scanstr.strip()
        scan_description={}
        scan_description['ScanString']=scanstr
        scan_description['RangeStrings']=[]

        # Hope there are no : in comment fields; should
        # instead use regexp.
        toks=scanstr.split(':')

        #print toks
        #print 'toks',toks[0]
        if toks[0].strip()!='Scan':
            raise ValueError('Not a Valid Scan: '+scanstr)
        toks=toks[1:]
        for tok in toks:
            idx = tok.find('=')
            if idx < 0:
                field,value = tok,''
            else:
                field,value = tok[:idx],tok[idx+1:]
            #print 'field',field
            if field=='':
                break  # for fpx scans can get a '::Title'  ack!!!!!!
            else:
                if field=='Range':
                    scan_description['RangeStrings'].append(tok)
                else:
                    try:
                        scan_description[field]=float(value)
                    except ValueError:
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        scan_description[field]=value

        self.scan_description = scan_description
        self.parse_ranges()

    def parse_ranges(self):
        """
        Parse all range strings.
        """
        Npoints = self.scan_description['Npts']
        self.ranges, self.oranges = {}, {}
        self.varying = []
        self.detector = self.scan_description['DetectorType']
        for range_string in self.scan_description['RangeStrings']:
            original,parsed=self.parse_one_range(range_string, Npoints)
            #print range_string
            #print original
            #print parsed
            #print
            self.ranges.update(parsed)
            self.oranges.update(original)
            # build up varying one field at a time to maintain order
            self.varying.extend([k for k in sorted(parsed.keys())
                                 if parsed[k]['step'] > VARYING_THRESHOLD])

    def interpret_range(self, tokens, Npoints):
        """
        Convert range parts into start, stop, step.

        Range can be (start,stop,'s'), (start,step,'i') or (center,step),
        where start,step,stop,center are string representations of floating
        point values.

        Npoints is the number of points in the range.

        Returns (original, parsed) where original has only the fields
        specified in the range, and parsed has start, step, stop with
        start<stop.
        """
        v1,v2 = float(tokens[0]),float(tokens[1])
        if tokens[-1] == 's':
            #print '<start> <stop> s'
            start,stop = min(v1,v2), max(v1,v2)
            step = (stop-start)/(Npoints-1) if Npoints > 1 else 0.
            original = {'start': v1, 'stop': v2}
            parsed = {'start': start, 'stop': stop, 'step': step}
        elif tokens[-1] == 'i':
            #print '<start> <increment> i'
            v3 = v1 + (Npoints-1)*v2  # find end of range
            start,stop = min(v1,v3),max(v1,v3)
            step = abs(v2)
            original = {'start': v1, 'step': v2}
            parsed = {'start': start, 'stop': stop, 'step': step}
        else:
            #print '<center> <step>'
            v3 = v2*(Npoints-1)/2 # find size of range
            start,stop = min(v1-v3,v1+v3), max(v1-v3,v1+v3)
            step = abs(v2)
            original = {'center': v1, 'step': v2}
            parsed = {'start': start, 'stop': stop, 'step': step, 'center': v1}
        return original, parsed

    def parse_one_range(self,rangestr,Npoints):
        """
        Parse a range string into start,stop,step.

        The string should have the form:

            Range=device=range

        where range is "start stop s", "start step i" or "start center".
        If device is 'Q', then QX,QY,QZ values are separated by '~' within
        start, stop, step and center.

        Returns { 'device': original }, { 'device': parsed }
        """
        if not rangestr.startswith('Range='):
            raise ValueError("Invalid range string "+rangestr)
        device, rangestr = rangestr[6:].split('=')
        tokens = rangestr.split()
        original, parsed = {}, {}
        if device == 'Q':
            v1,v2 = tokens[0].split('~'), tokens[1].split('~')
            if len(tokens) == 3:
                parts = zip(v1, v2, [tokens[2]]*3)
            else:
                parts = zip(v1, v2)
            for d,p in zip(('QX','QY','QZ'),parts):
                original[d], parsed[d] = self.interpret_range(p,Npoints)
        else:
            original[device], parsed[device] = self.interpret_range(tokens, Npoints)

        return original, parsed

# ============= Test cases ==============

_EXAMPLES, _EXPECTED_OUTPUT = zip(
    # 0: find peak, A3-A4
    ('Scan:Title=ICEFindPeak:Type=6:Fixed=0:FixedE=1:CountType=Time:\
Counts=2.0:Range=A4=50.0095 0.2:Npts=21:DetectorType=Detector:\
Filename=fpx:Range=A3=115.113 0.1::Title=FindPeak',
     {'A3': {'start': 114.113, 'step': 0.1, 'stop': 116.113, 'center': 115.113},
      'A4': {'start': 48.0095, 'step': 0.2, 'stop': 52.0095, 'center': 50.0095}}),
    # 1: inititial final h
    ('Scan:SubID=13176:JType=VECTOR:Fixed=1:FixedE=13.6998911684:Npts=3:\
Counts=1.0:Prefac=1.0:DetectorType=Detector:CountType=Time:Filename=dumb:\
HoldScan=0.0:Range=Q=1.0~0.0~0.0 2.0~0.0~0.0 s:Range=E=0.0 0.0 s',
     {'QY': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'QX': {'start': 1.0, 'step': 0.5, 'stop': 2.0},
      'QZ': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'E': {'start': 0.0, 'step': 0.0, 'stop': 0.0}}),
    # 2: initial step h
    ('Scan:SubID=13176:JType=VECTOR:Fixed=1:FixedE=13.6998911684:Npts=3:\
Counts=1.0:Prefac=1.0:DetectorType=Detector:CountType=Time:Filename=dumb:\
HoldScan=0.0:Range=Q=1.0~0.0~0.0 2.0~0.0~0.0 i:Range=E=0.0 0.0 i',
     {'QY': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'QX': {'start': 1.0, 'step': 2.0, 'stop': 5.0},
      'QZ': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'E': {'start': 0.0, 'step': 0.0, 'stop': 0.0}}),
    # 3: center step h
    ('Scan:SubID=13176:JType=VECTOR:Fixed=1:FixedE=13.6998911684:Npts=3:\
Counts=1.0:Prefac=1.0:DetectorType=Detector:CountType=Time:Filename=dumb:\
HoldScan=0.0:Range=Q=1.0~0.0~0.0 2.0~0.0~0.0:Range=E=0.0 0.0',
     {'QY': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'QX': {'start': -1.0, 'step': 2.0, 'stop': 3.0, 'center': 1.0},
      'QZ': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'E': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0}}),
    # 4: center step e [-1,0,1]
    ('Scan:SubID=13176:JType=VECTOR:Fixed=1:FixedE=13.6998911684:Npts=3:\
Counts=1.0:Prefac=1.0:DetectorType=Detector:CountType=Monitor:Filename=dumb:\
HoldScan=0.0:Range=Q=0.0~0.0~0.0 0.0~0.0~0.0:Range=E=0.0 1.0',
     {'QY': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'QX': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'QZ': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'E': {'start': -1.0, 'step': 1.0, 'stop': 1.0, 'center': 0.0}}),
    # 5: center step e [-.5,.5]
    ('Scan:SubID=13176:JType=VECTOR:Fixed=1:FixedE=13.6998911684:Npts=2:\
Counts=1.0:Prefac=1.0:DetectorType=Detector:CountType=Monitor:Filename=dumb:\
HoldScan=0.0:Range=Q=0.0~0.0~0.0 0.0~0.0~0.0:Range=E=0.0 1.0',
     {'QY': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'QX': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'QZ': {'start': 0.0, 'step': 0.0, 'stop': 0.0, 'center': 0.0},
      'E': {'start': -0.5, 'step': 1.0, 'stop': 0.5, 'center': 0.0}}),
    # 6: initial step e [0,1,2]
    ('Scan:SubID=13176:JType=VECTOR:Fixed=1:FixedE=13.6998911684:Npts=3:\
Counts=1.0:Prefac=1.0:DetectorType=Detector:CountType=Monitor:Filename=dumb:\
HoldScan=0.0:Range=Q=0.0~0.0~0.0 0.0~0.0~0.0 i:Range=E=0.0 1.0 i',
     {'QY': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'QX': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'QZ': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'E': {'start': 0.0, 'step': 1.0, 'stop': 2.0}}),
    # 7: start stop e [0,.5,1]
    ('Scan:SubID=13176:JType=VECTOR:Fixed=1:FixedE=13.6998911684:Npts=3:\
Counts=1.0:Prefac=1.0:DetectorType=Detector:CountType=Monitor:Filename=dumb:\
HoldScan=0.0:Range=Q=0.0~0.0~0.0 0.0~0.0~0.0 s:Range=E=0.0 1.0 s',
     {'QY': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'QX': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'QZ': {'start': 0.0, 'step': 0.0, 'stop': 0.0},
      'E': {'start': 0.0, 'step': 0.5, 'stop': 1.0}}),
    )

def test():
    for scanstr,output in zip(_EXAMPLES,_EXPECTED_OUTPUT):
        scan = parse_scan(scanstr)
        scan_varying = scan.varying
        expected_varying = [k for k,v in output.items() if v['step'] != 0]
        assert set(scan_varying) == set(expected_varying), scanstr
        scan_ranges = scan.ranges
        expected_ranges = output
        assert set(scan_ranges.keys()) == set(expected_ranges.keys()), \
            ("%s\nexpected %s but got %s"
             %(scanstr,set(expected_ranges.keys()),set(scan_ranges.keys())))
        for parameter,prange in expected_ranges.items():
            assert set(prange.keys()) == set(scan_ranges[parameter].keys()), \
                ("%s\nexpected %s but got %s"
                 %(scanstr,set(prange.keys()),set(scan_ranges[parameter].keys())))
            for k,v in prange.items():
                assert abs(v - scan_ranges[parameter][k]) < 1e-8, \
                       ("%s\nexpected %s.%s=%s but got %s"
                        %(scanstr,parameter,k,v,scan_ranges[parameter][k]))


def demo():
    for scanstr in _EXAMPLES:
        scan=parse_scan(scanstr)
        #scanstr_parsed=myparser.parse_scan()
        #print myparser.parse_range(scanstr_parsed['range_strings'][0])
        print scanstr
        print scan.varying
        print scan.ranges

if  __name__=='__main__':
    demo()
    test()
