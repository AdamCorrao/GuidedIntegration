# GuidedIntegration
Guided automated integration of 2D images to 1D XRD patterns using pyFAI
Includes both graphical user interface and command line interface options
Fully scriptable option available with integration selection based on either a keyword or GUI selection
  
  Citation for pyFAI: Jérôme Kieffer and Dimitrios Karkoulis 2013 J. Phys.: Conf. Ser. 425 202012 https://doi.org/10.1088/1742-6596/425/20/202012
  
  Github for pyFAI: https://github.com/silx-kit/pyFAI

Workflow for guided integration:

-In advance save calibration parameter file (.poni) and edge / beamstop mask (.tif) from pyFAI calibration

-Select option 1) guided integration, 2) full auto scripted integration, or 3) load .int file from prior guided integration use

1) GUI option: self-explanatory (follow prompts)
1) CLI option: self-explanatory (follow prompts)
2) Prompts GUI selection tool to load .py file (e.g., FullAutoIntegration.py) -> confirm script execution -> integration
3) Prompts GUI selection tool to load .int file (e.g., GuidedIntegration_18-Oct-2022_12:00:00.int) -> confirm integration prms -> select directories with 2D images to integrate -> integration

Notes to user:

-NSLS-II option filepath is as follows: tiff_base/samplename/dark_sub

-APS option has filepath options for 2D images contained in a single directory or multiple

To do prior to integration:

-Save calibration parameter file (.poni) and edge / beamstop mask (.tif) from pyFAI calibration

-If not using default integration parameters, choose the integration method, X units, number of radial points, etc.

Required libraries: pyFAI, tkfilebrowser, tkinter, scientific python libraries (numpy, pandas), tqdm
