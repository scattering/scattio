.. _bt7format:

***************
BT7 File Format
***************

BT7 is a triple axis spectrometer, with a monochromator, a filter,
an analyzer and a detector.
BT7 has a choice of detectors, one of which is the primary detector
for a scan.

The single detector (SD) is placed after the analyzer and integrates over
a range of Q for some delta E.  It is a cluster of three individual
detectors SD0-SD2 which are treated as a single value.

The position sensitive detector (PSD) is placed after the analyzer
and measures independent Q for some delta E.  This presents a series
of 48 detectors, PSD00-PSD47.

The door detector is placed in the direct path from the sample to
analyzer (or is it main beam?) and measures the elastic scattering
of the sample.  It is a group of 11 detectors (TD0-TD10), which are
often treated as a single value.

The diffraction detector (DD) is placed in front of the analyzer, close
to the sample and measures integrated intensity across Q and E.  It
is a cluster of three individual detectors DDC0-DDC2 which is treated
as one.


Ice Format
==========

BT7 data files are stored in the ICE data format.  These files can be
read using the :mod:`scattio.ncnr.iceformat`.

The ICE format files were generated on BT7 and MACS between 2007 and 2011.


Header Fields
=============

File information

    =================== =======================================================
    *InstrName*         Name of the instrument used
    *Filename*          <ScanBasename><ScanID>.<InstrumentName.lower()>
    *Date*, *Epoch*     Measurement start time as time.struct_time and as float
    *Comment*           Comment on measurement (used occasionally).
    =================== =======================================================

Experiment information

    *ExptID*, *ExptName*, *ExptDetails*,
    *ExptParticpants*, *ExptComment*

Scan information

    =================== =======================================================
    *ScanDescr*         text string provided by ICE describing the scan
    *ScanRanges*        dictionary with start, step, stop and maybe center
    *Npoints*           number of points in the scan
    *ScanId*            scan number (guessed from file name)
    *ScanVarying*       list of control column names
    *ScanTitle*         name of the scan
    *ScanComment*       additional scan details
    *ScanBasename*      base name for the saved file.
    *ScanType*          ANGLE|VECTOR|MOTOR|ENV|Find Peak Scan|Increment Scan|...
    =================== =======================================================

    The scan may have terminated early, so Npoints may be wrong.

	Only *ScanDescr*, *ScanRanges* and *Npoints* are stored directly. The ice
	data reader will fill in some fields (varying, ranges, title, comment) 
	from the scan description and others (id, basename) from the filename.
    Note that the original *ScanRanges* field in the file header is unreliable
    and is replaced by the information in *ScanDescr* by the ice reader.

Measurement information

    =================== =======================================================
    *Reference*         Count-by column (Time, Monitor or Detector)
    *Signal*            Primary Y axis (Detector, Monitor, DDC1, ...)
    *Scan*              Primary X axis (*ScanVarying* is more reliable)
    *Fixed*             Fixed devices (does not correspond to data columns)
    =================== =======================================================

Sample information

    =================== =======================================================
    *Lattice*           dictionary with a,b,c,alpha,beta,gamma
    *Orient1*,*Orient2* dictionary with h,k,l
    =================== =======================================================

Sample environment

    =================== =======================================================
    *TemperatureUnits*  units in the Temp column
    =================== =======================================================

Instrument configuration

    =================== =======================================================
    *FixedE*            Base energy for energy scans ('Ef|Ei', value)
    =================== =======================================================

    Energy scans vary Ei relative to a fixed Ef value, or Ef relative
    to a fixed Ei value.  *FixedE* reports which energy is fixed and
    what value it is fixed at.  Missing Ei and Ef columns in energy
    scan datasets can be reconstructed from E and FixedE.

    The fixed value for Ef and Ei come from a small number of preferred
    values depending on the properties of the monochromator, filter and
    analyzer. Pyrolytic graphite (PG) has good transmission at 13.7, 14.7,
    28, 30.5, 35 and 41.

    Fixed Ei=1 is common, but the values of *A1* and *A2* in those cases
    suggest that it is ignored.

    ==================================== ===============================================
    *AnalyzerDetectorMode*               Analyzer/detector configurations
    *AnalyzerDetectorDevicesOfInterest*  Device# Device# ...
    *AnaSpacing*                         1.278 A (Cu220) | 3.35416 A (PG002)
    *AnalyzerFocusMode*                  FLAT | ENERGY
    *AnalyzerSDGroup*                    Single detector devices (SDC0-2)
    *AnalyzerPSDGroup*                   Position sensitive detector devices (PSDC00-47)
    *AnalyzerDDGroup*                    Diffraction detector devices (DDC0-2)
    *AnalyzerDoorDetectorGroup*          Door detector devices (TDC00-TDC08)
    *PostAnaCollType*                    Post-analyzer collimator (RADIAL|SOLLER|OPEN)
    *PostAnaCollDivergence*              Collimator divergence in minutes, or 0 if Open
    ==================================== ===============================================


    *AnalyzerDetectorMode* is not set directly in the control program, but
    instead it is based on the detector group, focus type and
    rotation in use for the measurement.  Setting the detector
    group also sets the detector devices of interest, which are
    summed to produce the *Detector* column in the data.

    The mode names in AnalyzerDetectorMode correspond to the following
    choice of detector, AnalyzerFocus and AnalyzerRotation:

        ==== =========== ======== ============== ========
        Mode Name        Detector Focus          Rotation
        ==== =========== ======== ============== ========
           1 DiffDet     DD       FLAT or ENERGY
           2 SingDetFlat SD       FLAT
           3 SingDetHFoc SD       ENERGY
           4 PSDDiff     PSD      FLAT           90
           5 PSDFlat     PSD      FLAT           not 90
           6 Undefined   PSD      ENERGY
        ==== =========== ======== ============== ========


    *AnalyzerRotation* and *AnalyzerBlade##* values are computed from Ef,
    depending on the selected mode.

    In practice, diffraction mode is active whenever the diffraction
    detector is at position 180, even when the detector group is set
    to PSD.  Setting the official diffraction mode in the software
    parks the psd/single detector which can be inconvenient during
    an experiment.

	*PostAnaCollType* and *PostAnaCollDivergence* are inferred
	by the ice reader from the positions of the detectors and the collimator 
	motors at the first point in the data file, and may be incorrect if the
	collimation changes during the scan, or if the position of the collimators
	drifts over time.

    =========================== ==============================================
    *MonoVertiFocus*            FLAT | SAGITTAL
    *MonoHorizFocus*            FLAT | POINT | ENERGY | VENETIAN
    *MonoSpacing*               1.278 A (Cu220) | 3.35416 A (PG002)
    *PreMonoCollType*           Pre-monochromator collimator (SOLLER|OPEN)
    *PreMonoCollDivergence*     Collimator divergence in minutes, or 0 if Open
    =========================== ==============================================

    Monochromator d-spacing is determined by the monochromator elevator
    position.  Looking at the code, -344 should be PG and 0 should be Cu,
    with a cutoff of -100 to select between them.

    Monochromator translation, rotation, blade angle and focus are
    computed from Ei depending on the selected mode.  Focus is either
    FocusPG if the monochromator elevator is lowered or FocusCu if it
    is raised.

	*PreMonoCollType* and *PreMonoCollDivergence* are inferred
	by the ice reader from the value of *PreMonoColl* at the first point in 
	the data file, and may be incorrect if the value changes during the scan.

Miscellaneous

    ====================== ====================================================
    *ICE*                  ICE Version
    *ICERepositoryInfo*    Detailed ICE version
    *User*                 Which account was used to run the program
    *UBEnabled*            0
    *Columns*, *Ncolumns*  Data columns
    *DetectorDims*         not available
    *DetectorEfficiencies* Device#=value ...
    ====================== ====================================================

    *DetectorDims* should be 1 for SD and DD analyzer detector modes,
    and 48 for PSD mode.

    *DetectorEfficiencies* should give the nominal efficiency of each
    monitor and detector but values in the file appear to be set to 1.

Data Columns
============

Instrument geometry

    =================== =======================================================
    *A1*-*A6*           Real space geometry (degrees)
    *QX*, *QY*, *QZ*    Reciprocal space geometry relative to sample (1/Ang)
    *H*, *K*, *L*       Reciprocal space geometry relative to crystal
    *HKL*               Combined [H,K,L] formatted as a string. (redundant)
    *Ei*, *Ef*          Initial and final energy selection. (meV)
    *E*                 Energy relative to *Ei* or *Ef*, depending on *FixedE*
    =================== =======================================================

    Depending on mode each of these values can be computed from the
    others or can be a control value.

    By setting the monochromator in the specular condition with the 
    reflected angle A2 as twice the incident angle 2*A1, the selected
    Ei can be computed from A2 and the monochromator d-spacing using:

    .. math::

        E_i &=& h^2 / (2 n_m \lambda^2) \\
            &=& h^2 / (2 n_m (2 d sin(A_2/2))^2) \\
            &=& h^2 / (2 n_m d^2 (2 - 2 \cos A_2)) 

    This makes use of Bragg's law:
    
    .. math::
    
        2 d \sin \theta = n \lambda
        
    and the trignometric double angle formula
    
    .. math::
    
        2 \sin \theta = \sqrt{2 - 2 \cos (2 \theta)}
    
    Similarly for A5-A6, analyzer d-spacing and Ef.

    Use *DFMRot* instead of *A1* and *AnalyzerRotation* instead of *A5*.
    *A6* is also unreliable, and users should instead use *DiffDet*, 
    *SingleDet* or *PSDet* depending on which mode is in use.

Experiment monitors

    =================== =======================================================
    *Time*              Measurement duration (s)
    *Monitor*           Counts from monitor 1
    *Monitor2*          Counts from monitor 2
    *Detector*          Counts from detectors (AnalyzerDetectorDevicesOfInterest)
    *TimeStamp*         Time the measurement started (seconds since epoch)
    =================== =======================================================

    *Detector* is the integrated counts across all detectors in the primary
    detector group.  In older versions of ICE, *Detector* was called *Counts*,
    but this column will be converted automatically by the reader.

Instrument geometry

    =================== =======================================================
    *MonoElev*          Monochromator elevation (-344 for PG, 0 for Cu)
    *DFMRot*, *DFM*     Double Focusing Monochromator rotation (DFM is a copy)
    *MonoTrans*         Monochromator translation
    *MonoBlade##*       Monochromator blade positions 01-10
    *FocusCu*           Monochromator focus for Cu monochromator
    *FocusPG*           Monochromator focus for PG monochromator
    =================== =======================================================

    *MonoElev* shifts the monochromator assembly.  In one position, the Cu
    monochromator is in the beam path, and in another the PG monochromator
    is in the beam path.  *DFMRot*/*DFM* gives the angle of the
    monochromator relative to the source.  *A1* is set to this value unless
    the monochromator mode is unusual, in which case *A1* is undefined.

    *FocusCu* and *FocusPG* are computed from Ei based on monochromator mode.
    One should be able to compute the angles of individual y blades based
    on the value FocusCu/FocusPG, but in practice this information is not
    needed; when good vertical resolution is desired the monochromator is
    kept flat.
    
    =================== =======================================================
    *AnalyzerRotation*  Angle of the analyzer
    *AnalyzerBlade##*   Analyzer blade positions 01-13
    *SmplGFRot*         Sample guide field rotation (degrees)
    *SingleDet*,
    *DiffDet*,
    *PSDet*             Detector angles (degrees)
    =================== =======================================================

    *AnalyzerRotation* and *AnalyzerBlade##* are computed from Ef based
    on analyzer mode.  *AnalyzerRotation* is the angle of the analyzer
    relative to the sample. *A6* is set to *AnalyzerRotation* unless the
    blade angles are unusual, in which case *A6* is undefined.

    *SmplGFRot* is usually computed from 2theta, Ei and Ef

    Detector angles are set based on mode.??  Door detector is always in
    the direct path of the beam, so it doesn't need an angle.

Neutron filter

    ============================== ============================================
    *FilRot*, *FilTilt*, *FilTran* Filter position
    ============================== ============================================

Resolution

    ============================== ============================================
    *ApertHori*, *ApertVert*       Beam aperture
    *SmplHght*, *SmplWdth*         Front slits
    *BkSltHght*, *BkSltWdth*       Back slits
    *PreMonoColl*, *PostMonoColl*,
    *PreAnaColl*, *PostAnaColl*    Collimators
    *RC*, *SC*                     Soller and radial collimators (degrees)
    ============================== ============================================

    *PostMonoColl*, *PreAnaColl* are manual devices.

    *PreMonoColl* is one of OPEN, 50min, 25min and 10min.  Files may 
    use OPEN\_ instead of OPEN.
    
    *PostAnaColl* is not set. 
    
    BT7 has two independently controlled collimators (RC and SC)
    on the same rail between the analyzer and the detector.  The Soller 
    collimator device (SC) uses a different position for each 
    collimation (25', 50', 120'); the radial collimator (RC) has only one 
    active position.  The collimators must be positioned so that they do not 
    overlap each other or shadow the detector when they are not in use.

    In diffraction mode (DD=180) the diffraction detector is
    placed in front of the analyzer, so it doesn't matter where
    the post analyzer collimators (RC, SC) or detectors (SD, PSD)
    are located.

    Modes observed on BT7 in 2010-2011:

        Single detector modes (DD=198  PSD=-85)

        ===== ========= =========== ====================================
        OPEN  RC = 238  SC =   79
        SC1   RC = 243  A6-SC = 0
        SC2   RC = 243  A6-SC = 45
        SC3   RC = 243  A6-SC = 67
        ===== ========= =========== ====================================


        PSD Modes (PSD=41  SD=145  DD=205)

        ===== ========= =========== ====================================
        OPEN  RC = 257  SC = 65     shades one end of the psd
        OPEN  RC = 259  SC = 63     shades the other end of the psd
        OPEN  RC = 110  SC = -110   ??
        RC    A6-RC = 0 SC = -110
        ===== ========= =========== ====================================


        Diffraction mode (DD=180  PSD/SD=anywhere)

        ===== ========= =========== ====================================
        OPEN  RC = any  SC = any
        ===== ========= =========== ====================================

    These values are approximate, and have changed over time.

    The file loader tries to guess the collimator used for the file
    from the data.

Sample orientation

    ============================ ==============================================
    *SmplElev*,
    *SmplLTilt*, *SmplLTrn*,
    *SmplUTilt*, *SmplUTrn*      Control parameters for aligning the sample
    ============================ ==============================================

Sample environment

    =================== =======================================================
    *Temp*              Temperature
    *MagField*          Magnetic field
    *Pressure*          Pressure
    =================== =======================================================

    Measured sample environment

    ============================ ==============================================
    *TemperatureSetpoint*        Target temperature
    *TemperatureHeaterPower*     Heater power
    *TemperatureControlReading*
    *TemperatureSensor#*         Sensors 0, 1, 2, and 3
    ============================ ==============================================


    Raw temperature controller fields.

Polarizers

    ========================== ================================================
    *Flip*                     Polarization state? A=--, B=-+, C=+-, D=++
    *Hsample*, *Vsample*       Horizontal and vertical guide field at the sample.
    *EIcancel*, *EFcancel*     Front/back cancellation field current
    *EIflip*, *EFflip*         Front/back flipper current
    *EIguide*, *EFguide*       Front/back guide field current
    ========================== ================================================

    Flipper, guide field and cancellation field currents.
    *EIflip* seems to depend on *A6*.

Detectors

    =================== =======================================================
    *SDC#*              single detector 0, 1, 2
    *PSDC##*            position sensitive detector 00-47
    *DDC#*              diffraction detector 0, 1, 2
    *TDC##*             transmission or door detector 00-08
    =================== =======================================================

    Measured counts on each detector
