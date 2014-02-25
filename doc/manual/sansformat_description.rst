.. _sansformat:

****************
SANS File Format
****************

The NCNR SANS file format is a binary file format with fixed structure.

Floating point numbers use the four byte VAX representation.  To convert
vax to little endian IEEE 754, use the following transformation::

    ieee[0] = vax[2]
    ieee[1] = vax[3]
    ieee[2] = vax[0]
    ieee[3] = vax[1]-1 if vax[1]!=0 else 0

and the other direction:

    vax[0] = ieee[2]
    vax[1] = ieee[3]+1 if not all(ieee==0) else 0
    vax[2] = ieee[0]
    vax[3] = ieee[1]

Integers and unsigned integers are four byte little endian.

Strings are padded with blanks to the full length.

Fields needed for IGOR reduction are marked using *field*.

The following fields are defined:

    ============================================================================
    fname
    ============ === ======== ==================================================
    filename       2 char[21] File name
    ============ === ======== ==================================================
     
    ============================================================================
    run
    ============ === ======== ==================================================
    npre          23 int      number of run prefactors
    ctime         27 int      count time per prefactor
    *rtime*       31 int      total count time (s)
    numruns       35 int      
    *moncnt*      39 float    monitor count
    savmon        43 float
    *detcnt*      47 float    detector count (from the anode plane)
    *atten*       51 float    attenuator number (not transmission)
    *datetime*    55 char[20] data and time of collection DD-MMM-YYYY HH:MM:SS
    type          75 char[3]  'RAW'
    defdir        78 char[11] NGxSANSnn
    mode          89 char[1]  counting mode
                              VAX software: C or M
                              ICE: 0 for monitor, 1 for detector?
                              NICE: 1-8, with 1=time, 2=monitor, 4=detector
    reserve       90 char[8]  date formatted as DDMMMYY with trailing space
    ============ === ======== ==================================================

    ============================================================================
    sample
    ============ === ======== ==================================================
    *labl*        98 char[60] sample label
    trns         158 float    sample transmission (default is 1.0)
    *thk*        162 float    sample thickness (cm)
    *position*   166 float    sample changer position
    *rotang*     170 float    sample rotation angle (degrees)
    table        174 int      chamber or huber position
    holder       178 int      sample holder identifier
    blank        182 int
    *temp*       186 float    temperature (C)
    field        190 float    applied field strength (sample.funits).*
    tctrlr       194 int      sample control identifier
    magnet       198 int      magnet identifier
    tunits       202 char[6]  temperature units (assumed to be C by IGOR)
    funits       208 char[6]  applied field units
    ============ === ======== ==================================================

    \* Igor code NCNR_User_Procedures/Reduction/SANS/NCNR_DataReadWrite.ipf 
    says:
	
	    190 is not the right location, 348 looks to be correct for the 
	    electromagnets, 450 for the superconducting magnet.  Although each
	    place is only the voltage, it is correct

    ============================================================================
    det
    ============ === ======== ==================================================
    typ          214 char[6]  detector type (ORNL or ILL)
    *calx1*      220 real     detector x pixel size (mm)
    calx2        224 real     10000   non-linear spatial corrections
    calx3        228 float    0
    *caly1*      232 float    detector y pixel size (mm)
    caly2        236 float    10000
    caly3        240 float    0
    num          244 int      area detector identifier
    spacer       248 int    
    beamx        252 float    beam center x position (detector coord)
    beamy        256 float    beam center y position (detector coord)
    *dis*        260 float    sample to detector distance (m)
    *ang*        264 float    horizontal detector offset (cm)
    siz          268 float    physical detector width (cm)
    *bstop*      272 float    beam stop diameter (mm)
    blank        276 float    
    ============ === ======== ==================================================

    ============================================================================
    resolution
    ============ === ======== ==================================================
    *ap1*        280 float    source aperture diameter (mm)
    *ap2*        284 float    sample aperture diameter (mm)
    *ap12dis*    288 float    source aperature to sample aperture distance (m)
                              nGuides = round(ap12dis*100+5-1632)/-155 
    *lmda*       292 float    wavelength (A)
    *dlmda*      296 float    wavelength spread (FWHM)
    save         300 float    lens flag
    ============ === ======== ==================================================
     
    ============================================================================
    tslice
    ============ === ======== ==================================================
    slicing      304 uint    
    multfact     308 int      multiplicative factor for slicing bins
    ltslice      312 int    
    ============ === ======== ==================================================
     
    ============================================================================
    temp
    ============ === ======== ==================================================
    printemp     316 uint     print temp after prefactor
    hold         320 float    
    err          324 float    
    blank        328 float    
    extra        332 int      0x0001 print blue box temp;
                              0x0100 control from int. bath or ext. probe
    reserve      336 int    
    ============ === ======== ==================================================
     
    ============================================================================
    magnet
    ============ === ======== ==================================================
    printmag     340 uint    
    sensor       344 uint    
    *current*    348 float    magnetic field
    conv         352 float    
    fieldlast    356 float    
    blank        360 float    
    spacer       364 float    
    ============ === ======== ==================================================
     
    ============================================================================
    bmstp
    ============ === ======== ==================================================
    *xpos*       368 float    beam stop X position (MCU app. cm)
    *ypos*       372 float    beam stop Y position (MCU app. cm)
    ============ === ======== ==================================================
     
    ============================================================================
    params
    ============ === ======== ==================================================
    blank1       376 int    
    blank2       380 int    
    blank3       384 int    
    trsncnt      388 float    transmission detector count
    extra1       392 float    whole detector transmission
    extra2       396 float    
    extra3       400 float    
    reserve      404 char[42] first four characters are associated file suffix
    ============ === ======== ==================================================
     
    ============================================================================
    voltage
    ============ === ======== ==================================================
    printvolt    446 uint    
    volts        450 float    field strength for the superconducting magnet
    blank        454 float    
    spacer       458 int    
    ============ === ======== ==================================================
     
    ============================================================================
    polarization
    ============ === ======== ==================================================
    printpol     462 uint    
    flipper      466 uint    
    horiz        470 float    
    vert         474 float    
    ============ === ======== ==================================================
     
    ============================================================================
    analysis*
    ============ === ======== ==================================================
    rows1        478 int      box x1  (user defined tranmsission est. box)
    rows2        482 int      box x2
    cols1        486 int      box y1
    cols2        490 int      box y2
    factor       494 float    box counts
    qmin         498 float    
    qmax         502 float    
    imin         506 float    
    imax         510 float    
    ============ === ======== ==================================================

    * These values are written by the reduction program
