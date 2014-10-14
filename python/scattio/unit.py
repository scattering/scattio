# This program is public domain
# -*- coding: UTF-8 -*-
# Author: Paul Kienzle
"""
Define unit conversion support for NeXus style units.

The unit format is somewhat complicated.  There are variant spellings
and incorrect capitalization to worry about, as well as forms such as
"mili*metre" and "1e-7 seconds".

This is a minimal implementation.  It does not support the complete 
dimensional analysis provided by the package UDUnits on which NeXus is 
based, or even all the units used in the NeXus definition files.

Unlike other units modules, this module does not carry the units along
with the value, but merely provides a conversion function for
transforming values.

Usage example::

    import nxs.unit
    u = nxs.unit.Converter('mili*metre')  # Units stored in mm
    v = u(3000,'m')  # Convert the value 3000 mm into meters

NeXus example::

    # Load sample orientation in radians regardless of how it is stored.
    # 1. Open the path
    file.openpath('/entry1/sample/sample_orientation')
    # 2. scan the attributes, retrieving 'units'
    units = [value for attr,value in file.attrs() if attr == 'units'][0]
    # 3. set up the converter (assumes that units actually exists)
    u = nxs.unit.Converter(units)
    # 4. read the data and convert to the desired units
    v = u(file.read(),'radians')

The converter knows the dimension it is working with.  For example, if
the dimension is time, then u(300,'hour') will return the time in hours,
but if the dimension is angle, then u(300,'hour') will raise an error.
Using minutes will work in both cases.  When constructing a converter,
you may need to specify a dimension.  For example, Converter('second')
will create a time converter, but Converter('second','angle') will create
an angle converter.

The list of ambiguities, and the default dimension is given in the 
unit.AMBIGUITIES map.  The available dimensions and the conversion factors
are given in the unit.DIMENSIONS map.  Note that the temperature converters
have a scale and an offset rather than just a scale.

This is a standalone module, not relying on NeXus, and can be used for 
other unit conversion tasks.
"""

# UDUnits:
#  http://www.unidata.ucar.edu/software/udunits/udunits-1/udunits.txt

from __future__ import division

__all__ = ['Converter']

import math


# Limited form of units for returning objects of a specific type.
# Maybe want to do full units handling with e.g., pyre's
# unit class. For now lets keep it simple.  Note that
def _build_metric_units(unit,abbr):
    """
    Construct standard SI names for the given unit.
    Builds e.g.,
        s, ns
        second, nanosecond, nano*second
        seconds, nanoseconds
    Includes prefixes for femto through peta.

    Ack! Allows, e.g., Coulomb and coulomb even though Coulomb is not
    a unit because some NeXus files store it that way!

    Returns a dictionary of names and scales.
    """
    prefix = dict(peta=1e15,tera=1e12,giga=1e9,mega=1e6,kilo=1e3,
                  deci=1e-1,centi=1e-2,milli=1e-3,mili=1e-3,micro=1e-6,
                  nano=1e-9,pico=1e-12,femto=1e-15)
    short_prefix = dict(P=1e15,T=1e12,G=1e9,M=1e6,k=1e3,
                        d=1e-1,c=1e-2,m=1e-3,u=1e-6,
                        n=1e-9,p=1e-12,f=1e-15)
    map = {abbr:1}
    map.update([(P+abbr,scale) for (P,scale) in short_prefix.iteritems()])
    for name in [unit,unit.capitalize()]:
        map.update({name:1,name+'s':1})
        map.update([(P+name,scale) for (P,scale) in prefix.iteritems()])
        map.update([(P+'*'+name,scale) for (P,scale) in prefix.iteritems()])
        map.update([(P+name+'s',scale) for (P,scale) in prefix.iteritems()])
    return map

def _build_plural_units(**kw):
    """
    Construct names for the given units.  Builds singular and plural form.
    """
    map = {}
    map.update([(name,scale) for name,scale in kw.iteritems()])
    map.update([(name+'s',scale) for name,scale in kw.iteritems()])
    return map

def _build_degree_units(name, symbol, conversion):
    """
    Builds variations on the temperature unit name, including the degree
    symbol or the word degree.
    """
    map = {}
    map[symbol] = conversion
    for s in symbol, symbol.lower():
        map['deg'+s] = conversion
        map['deg_'+s] = conversion
        map['deg '+s] = conversion
        map['°'+s] = conversion
    for s in name, name.capitalize(), symbol, symbol.lower():
        map[s] = conversion
        map['degree_'+s] = conversion
        map['degree '+s] = conversion
        map['degrees '+s] = conversion
    return map

def _build_inv_units(names, conversion):
    """
    Builds variations on inverse units, including 1/x, invx and x^-1.
    """
    map = {}
    for s in names:
        map['1/'+s] = conversion
        map['inv'+s] = conversion
        map[s+'^-1'] = conversion
    return map

def _build_inv2_units(names, conversion):
    """
    Builds variations on inverse square units, including 1/x^2, invx^-2 and x^-2.
    """
    map = {}
    for s in names:
        map['1/'+s+'^2'] = conversion
        map['inv'+s+'^2'] = conversion
        map[s+'^-2'] = conversion
    return map
    

def _build_all_units():
    """
    Fill in the global variables DIMENSIONS and AMBIGUITIES for all available
    dimensions.
    """
    # Gather all the ambiguities in one spot
    AMBIGUITIES['A'] = 'distance'     # distance, current
    AMBIGUITIES['second'] = 'time'    # time, angle
    AMBIGUITIES['seconds'] = 'time'
    AMBIGUITIES['sec'] = 'time'
    AMBIGUITIES['°'] = 'angle'        # temperature, angle
    AMBIGUITIES['minute'] = 'angle'   # time, angle
    AMBIGUITIES['minutes'] = 'angle'
    AMBIGUITIES['min'] = 'angle'
    AMBIGUITIES['C'] = 'charge'       # temperature, charge
    AMBIGUITIES['F'] = 'temperature'  # temperature
    AMBIGUITIES['R'] = 'radiation'    # temperature:rankines, radiation:roentgens
    
    # Various distance measures
    distance = _build_metric_units('meter','m')
    distance.update(_build_metric_units('metre','m'))
    distance.update(_build_plural_units(micron=1e-6, Angstrom=1e-10, angstrom=1e-10))
    distance.update({'A':1e-10, 'Ang':1e-10, 'ang':1e-10, 'Å':1e-10})
    DIMENSIONS['distance'] = distance

    # Various time measures.
    # Note: months/years are varying length so can't be used without date support
    time = _build_metric_units('second','s')
    time.update(_build_plural_units(minute=60,hour=3600,day=24*3600,week=7*24*3600))
    time.update({'sec':1, 'min':60, 'hr':3600})
    time.update({'1e-7 s':1e-7, '1e-7 second':1e-7, '1e-7 seconds':1e-7})
    DIMENSIONS['time'] = time

    # Various angle measures.
    angle = _build_plural_units(
        degree=1, minute=1/60., second=1/3600.,
        arcdegree=1, arcminute=1/60., arcsecond=1/3600.,
        radian=180/math.pi)
    angle.update(
        deg=1, min=1/60., sec=1/3600.,
        arcdeg=1, arcmin=1/60., arcsec=1/3600., 
        angular_degree=1, angular_minute=1/60., angular_second=1/3600., 
        rad=180/math.pi,
        )
    angle['°']=1
    DIMENSIONS['angle'] = angle

    frequency = _build_metric_units('hertz','Hz')
    frequency.update(_build_plural_units(rpm=1/60.))
    frequency.update(_build_inv_units(('s',),1))
    DIMENSIONS['frequency'] = frequency

    # Note: degrees are used for angle
    temperature = _build_metric_units('kelvin','K')
    for k,v in temperature.items():
        temperature[k] = (v,0)  # add offset 0 to all kelvin temperatures
    temperature.update(_build_degree_units('celcius','C',(1,273.15)))
    temperature.update(_build_degree_units('centigrade','C',temperature['degC']))
    temperature.update(_build_degree_units('fahrenheit','F',(5./9.,491.67-32)))
    temperature.update(_build_degree_units('rankine','R',(5./9.,0)))
    # special unicode symbols for fahrenheit and celcius
    temperature['℃'] = temperature['degC']
    temperature['℉'] = temperature['degF']
    DIMENSIONS['temperature'] = temperature

    charge = _build_metric_units('coulomb','C')
    charge.update({'microAmp*hour':0.0036})
    DIMENSIONS['charge'] = charge


    sld = _build_inv2_units(('Å','A','Ang','Angstrom','ang','angstrom'), 1)
    sld.update(_build_inv2_units(('nm',), 100))
    sld['10^-6 Angstrom^-2'] = 1e-6
    DIMENSIONS['sld'] = sld
    
    Q = _build_inv_units(('Å','A','Ang','Angstrom','ang','angstrom'), 1)
    Q.update(_build_inv_units(('nm',), 10))
    Q['10^-3 Angstrom^-1'] = 1e-3
    DIMENSIONS['Q'] = Q

    energy = _build_metric_units('electronvolt','eV')
    DIMENSIONS['energy'] = energy
    # Note: energy <=> wavelength <=> velocity requires a probe type

    # APS files may be using 'a.u.' for 'arbitrary units'.  Other
    # facilities are leaving the units blank, using ??? or not even
    # writing the units attributes.
    unknown = {None:1, '???':1, '': 1, 'a.u.':1}
    DIMENSIONS['dimensionless'] = unknown

# Initialize DIMENSIONS and AMBIGUITIES
DIMENSIONS = {}
AMBIGUITIES = {}
_build_all_units()

class Converter(object):
    """
    Unit converter for NeXus style units.
    
    The converter is initialized with the units of the source value.  Various
    source values can then 
    """
    def __init__(self, units, dimension=None):
        self.units = units
        
        # Lookup dimension if not given
        if dimension:
            self.dimension = dimension
        elif units in AMBIGUITIES:
            self.dimension = AMBIGUITIES[units]
        else:
            for k,v in DIMENSIONS.items():
                if units in v:
                    self.dimension = k
                    break
            else:
                self.dimension = 'unknown'

        # Find the scale for the given units
        try:
            self.scalemap = DIMENSIONS[self.dimension]
            self.scalebase = self.scalemap[self.units]
        except KeyError:
            raise ValueError('Unable to find %s in dimension %s'%(self.units,self.dimension))

    def __call__(self, value, units=""):
        # Note: calculating a*1 rather than simply returning a would produce
        # an unnecessary copy of the array, which in the case of the raw
        # counts array would be bad.  Sometimes copying and other times
        # not copying is also bad, but copy on modify semantics isn't
        # supported.
        if units == "" or self.scalemap is None: return value
        try:
            inscale,outscale = self.scalebase,self.scalemap[units]
            return value * inscale / outscale
        except KeyError:
            raise KeyError("%s not in %s"%(units," ".join(sorted(self.scalemap.keys()))))
        except TypeError:
            # For temperatures, a type error is raised because the conversion
            # factor is (scale, offset) rather than scale.
            inscale,inoffset = self.scalebase
            outscale,outoffset = self.scalemap[units]
            #print self.dimension, self.units, units
            #internal = (value+inoffset)*inscale
            #print value, internal, internal/outscale, internal/outscale - outoffset
            return (value+inoffset)*inscale/outscale - outoffset

def _check(expect,get):
    if abs(expect - get) > 1e-10*(abs(expect)+abs(get)):
        raise ValueError, "Expected %s but got %s"%(expect,get)
    #print expect,"==",get

def test():
    _check(2,Converter('mm')(2000,'m')) # 2000 mm -> 2 m
    _check(0.003,Converter('microseconds')(3,units='ms')) # 3 us -> 0.003 ms
    _check(45,Converter('nanokelvin')(45))  # 45 nK -> 45 nK
    _check(0.045,Converter('nanokelvin')(45,'uK'))  # 45 nK -> 0.045 uK
    _check(0.5,Converter('seconds')(1800,units='hours')) # 1800 -> 0.5 hr
    _check(2.5,Converter('a.u.')(2.5,units=''))
    _check(32,Converter('degC')(0,'degF')) # 0 C -> 32 F
    _check(373.15,Converter('degF')(212,'K')) #  212 F -> 373.15 K
    _check(-40,Converter('degF')(-40,'degC')) # -40 F = -40 C
    _check(2,Converter('1/A')(20,'nm^-1'))

if __name__ == "__main__":
    test()
