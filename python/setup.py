#!/usr/bin/env python

from distutils.core import setup

setup(name='ScattIO',
      version='0.1.0',
      description='Data readers for scattering file formats.\nCurrently provides python readers for NCNR data formats.Python Reflectometer Control System',
      author='Paul Kienzle',
      author_email='pkienzle@nist.gov',
      url='https://github.com/scattering/scattio',
      packages=['scattio',
        'scattio.examples.ng7',
        'scattio.examples.sans'],
     )
