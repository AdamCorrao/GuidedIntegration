# GuidedIntegration
Guided automated integration of 2D images to 1D patterns using pyFAI
Includes both graphical user interface and command line interface options

    Citation: Guided Integration Version 0.1 (2023). https://github.com/adamcorrao/GuidedIntegration
    Citation for latest paper on pyFAI: Kieffer, J., Valls, V., Blanc, N. & Hennig, C. (2020). J. Synchrotron Rad. 27, 558-566.

Functionality:
    -Guided setup for automated integration of 2D images to 1D patterns using pyFAI
    -Loading of integration (.int) text file for routine use (not recommended for 1st time users and those unfamiliar with pyFAI)
    -GUI and command line interface options for selecting directories to parse for images to integrate
    -Automates creation of separate directories for 1D patterns in a specified directory for each image directory selected
    -Saves an editable integration (.int) text file for easy parameter editing and routine use
    -Generates a record (.rec) file containing a list of directories parsed, a list of images integrated, and info from .int file**

To do prior to integration:
    -Save an instrument geometry file (.poni) from calibration (e.g., pyFAI-calib2)
    -Create a mask if needed (e.g., for detector edges, beamstop, dead pixels) and save as one of the following filetypes: *.tif | *.edf | *.npy | *.msk

Required libraries:
    -Scientific python libraries (e.g., numpy, pandas)
    -pyFAI (& all dependencies)
    -tkfilebrowser
    -tqdm

Notes to user:
    -NSLS-II filepath assumes 2D images are in subfolders as follows: tiff_base/samplename/dark_sub
    -APS/SSRL filepath has options for 2D images contained in a single directory or multiple