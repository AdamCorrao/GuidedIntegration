'''
Author: Adam A. Corrao
Date created: October 2021.
#Github: github.com/AdamCorrao/GuidedIntegration
#Citation: Guided Integration Version 0.1 (2023). https://github.com/adamcorrao/GuidedIntegration
#Citation for latest paper on pyFAI: Kieffer, J., Valls, V., Blanc, N. & Hennig, C. (2020). J. Synchrotron Rad. 27, 558-566.

Functionality:
-Guided setup for automated integration of 2D images to 1D patterns using pyFAI
-Loading of integration (.int) text file for routine use (not recommended for 1st time users and those unfamiliar with pyFAI)
-GUI and command line interface options for selecting directories to parse for images to integrate
-Automates creation of separate directories for 1D patterns in a specified directory for each image directory selected
-Saves an editable integration (.int) text file for easy parameter editing and routine use
-Generates a record (.txt) file containing a list of directories parsed, a list of images integrated, and info from .int file

To do prior to integration:
-Save an instrument geometry file (.poni) from calibration (e.g., pyFAI-calib2)
-Create a mask if needed (e.g., for detector edges, beamstop, dead pixels) and save as one of the following filetypes: *.tif | *.edf | *.npy | *.msk

Required libraries:
-Scientific python libraries (e.g., numpy, pandas)
-pyFAI
-tkfilebrowser
-tqdm

Future additions:
-Expanded integration method options beyond pixel splitting (e.g., algorithm selection, integration on GPU)
-Azimuthal variance error model - error not calculated when this method is chosen
'''
import fabio
import pyFAI
import os
import ast
from colorama import Fore, Back, init
from time import time
from time import sleep
from datetime import datetime
from tqdm import tqdm
import pandas as pd
import tkfilebrowser
from tkinter import *
import sys
init(autoreset=True)  # autoresets colors to default after colored print statements
os.system('cls')
Version = '0.1'

# Default integration parameters (arguments to be used in pyFAI int / .xy conversion)
d_intmethod = 'full'  # full pixel splitting method, change as needed: no, full, bbox, pseudo
d_xunit = '2th_deg'  # integrates images to 2theta space, change as needed: q_nm^-1 , q_A^-1, 2th_rad, r_mm, d*2_A^-2 etc.
d_rad_points = int(6000)  # number of radial points to integrate 2D image over
d_rad_range = None  # Radial (X) range to be provided as tuple [float, float] in X units - defaults to None for min, max
d_azim_range = None  # Azimuthal range (deg.) to integrate image over, provided as tuple [float, float] - defaults to None for full (360 deg.) range
d_neg_mask = float(-1e-10)  # auto-masks pixels in 2D image below this value (all negative pixels)
d_errormodel = 'None'  # intensity error model, change to 'poisson' for variance = I
d_lines2skip = int(23)  # number of lines to skip in pyFAI generated 1D file - these contain int / calib info

#Use python lower or upper function to normalize text input for matching input
intmethod_accepted = ['no', 'full', 'pseudo', 'bbox']
xunit_accepted = ['2th_deg', '2th_rad', 'q_nm^-1', 'q_A^-1', 'q_a^-1', 'r_mm']
neg_mask_accepted = ['none']
errormodel_accepted = ['none', 'poisson']
keyword_all_accepted = ['ALL','All','all']
maskfext_accepted = ['.tif','.edf','.msk','.npy']

#Boolean logic to reset up front - DO NOT EDIT
GUItiffs = False
CLItiffs = False

#Default directory name for 1D patterns if user does not provide directory
oneDdefault = '1D'

###########################################Guided integration selection#################################################
print(Fore.GREEN + "Welcome to Guided Integration\n\n" + Fore.WHITE + "\tHow-to:"
      "\n\t-Prior to Guided Integration, use pyFAI calib tools to save instrument geometry (.poni) and mask files"
      "\n\t-Follow guided integration to setup integration (.int) file"
      "\n\t-User responds to prompts with an input followed by the Enter key to make a selection"
      "\n\t-GUI and command line interface options for selecting directories to parse for images to integrate"
      "\n\t-Auto generated integration (.int) file is a text file that can be edited following the format provided"
      "\n\n\t*For 1st time users, please read the README.md before running Guided Integration*\n")
input(Fore.GREEN + 'Press Enter to begin...\n\n')
guideduse = input(Fore.YELLOW + "Would you like to use guided integration or load an integration (.int) file?"
                                "\n\t[1] for guided integration (full setup - highly recommended for 1st time users)"
                                "\n\t[2] to load integration (.int) file\n\n")
                               #"\n\t[3] to load scriptable auto integration (GUI tool to select .py script)\n")
############################################Start of guided integration#################################################
if guideduse == '1':
    print(Fore.GREEN + '\nProceeding with guided integration setup\n\n')

    synsrcq = input(Fore.YELLOW + 'Is the data to be integrated from NSLS-II, APS, or SSRL?\n\t[1] for NSLS-II '
                                  '(Expected filepath / type: tiff_base/Sample/dark_sub/scan.tiff)\n\t[2] for APS or '
                                  'SSRL (Expected filepath / type: GUP#####/Sample/scan.tif)\n\n')
    if synsrcq == '1':
        print(Fore.GREEN + '\nData in NSLS-II format\n')
        synsrc = 'NSLS-II'
        image_extension = '.tiff'
    elif synsrcq == '2':
        print(Fore.GREEN + '\nData in APS / SSRL format\n')
        synsrc = 'APS'
        image_extension = '.tif'
    else:
        print(Back.RED + 'Input not accepted - must be 1 for NSLS-II or 2 for APS / SSRL\n'
                         'Quitting setup - please restart')
        sys.exit()
        ##########################################Tiff directory selection #############################################
    tiffselect = input(Fore.YELLOW + "\nWould you like to select directories to integrate via a GUI file browser\nor "
                                     "through a command line interface (keyword-based)?\n\t[1] for GUI selection "
                                     "tool\n\t[2] for command line interface (keyword-based)\n")
    # GUI tiff selection
    if tiffselect == "1":
        print(Fore.CYAN + "\nPlease select the folders that you would like to integrate.\nNote: for NSLS-II select the "
                          "parent directories to 'dark_sub'\n")
        fulldirstoint = tkfilebrowser.askopendirnames(initialdir='', title="Select folders to integrate")
        if not fulldirstoint:
            print(Back.RED + 'Selection cancelled, quitting program\nPlease restart\n')
            sys.exit()
        else:
            dirstoint = []
            for dir in fulldirstoint:  # This loop makes a list with just the folder names, not full paths
                f = dir.split(os.sep)[-1]
                dirstoint.append(f)

            if len(dirstoint) == 1:
                print(Fore.GREEN + '\nFolder selected to integrate:')
                for f in dirstoint:
                    print('\t' + f)

            elif len(dirstoint) > 1:
                print(Fore.GREEN + '\n' + str(len(dirstoint)) + ' folders selected to integrate:')
                for f in dirstoint:
                    print('\t' + f)
            GUItiffs = True
            CLItiffs = False
        tiff_dir = fulldirstoint[0].partition(dirstoint[0])[0].rsplit(os.sep, 1)[0]
        main_dir = tiff_dir.rsplit(os.sep, 1)[0]
        print(Fore.GREEN + '\nMain directory:\n\t' + Fore.WHITE + main_dir + Fore.GREEN + '\nTiff directory:\n\t'
              + Fore.WHITE + tiff_dir + '\n')

    # CLI tiff selection based on keyword
    elif tiffselect == "2":
        # First we need to pick the directory where folders containing tiffs are
        print(Fore.CYAN + "\nPlease select the directory that contains folders with images to integrate"
              + Fore.WHITE + "\nExample:\n\tParent tiff directory = 'C:\\User\\Data\\BeamlineExperiment1\\tiff_base'"
                             "\n\tFolder to integrate = 'C:\\User\\Data\\BeamlineExperiment1\\tiff_base\\Sample1'\n")
        tiff_dir = tkfilebrowser.askopendirname(initialdir='',
                                                title="Select parent tiff directory - see prompt for examples")
        if not tiff_dir:
            print(Back.RED + 'Selection cancelled, quitting program\nPlease restart\n')
            sys.exit()
        else:
            main_dir = tiff_dir.rsplit(os.sep, 1)[0]
            print(Fore.GREEN + 'Main tiff directory selected:\n\t' + Fore.WHITE + tiff_dir + '\n')
            print(Fore.GREEN + 'Main directory:\n\t' + Fore.WHITE + main_dir + '\n')
        #Next we accept the keyword
        keyword = input(Fore.YELLOW + "What keyword is present in the folder names containing files you would like"
                        " to integrate?\n\tEx: 'LiCl' is a keyword for 'Fe3LiCl_100Cannealed'\n\tNote: enter 'ALL'"
                        " to select all sub-directories containing images to integrate\n")
        print('\nThe keyword is: ', keyword)
        keywordcorrect = input(Fore.YELLOW + "\nIs the keyword correct?\n\t[1] for correct\n\t[2] for incorrect, redo"
                                             "\n\t[3] for incorrect, quit program\n")
        if keywordcorrect == '1':
            print(Fore.GREEN + 'Keyword confirmed to be correct\n')
            GUItiffs = False
            CLItiffs = True
        if keywordcorrect == '2':
            keyword = input(Fore.YELLOW + "What keyword is present in the folder names containing files you would "
                                          "like to integrate?\n\tEx: 'LiCl' is a keyword for 'Fe3LiCl_100Cannealed'"
                                          "\n\tNote: enter 'ALL' to select all sub-directories containing images to"
                                          " integrate\n")
            print('\nThe keyword is: ', keyword)
            keywordcorrect = input(Fore.YELLOW + "\nIs the keyword correct?\n\t[1] for correct\n\t[2] for incorrect, "
                                                 "quit program\n")
            if keywordcorrect == '1':
                print(Fore.GREEN + 'Keyword confirmed to be correct\n')
                GUItiffs = False
                CLItiffs = True
            if keywordcorrect == '2':
                print(Back.RED + 'Quitting program\nPlease restart\n')
                sys.exit()
        if keywordcorrect == '3':
            print(Back.RED + 'Quitting program\nPlease restart\n')
            sys.exit()
    elif tiffselect != '1' and tiffselect != '2':
        print(Back.RED + 'Invalid input - quitting program\nPlease restart\n')
        sys.exit()
    ################################################Parent 1D directory selection###################################
    # 1D directory select
    print(Fore.CYAN + "Please select the parent directory for integrated patterns to be saved\n" + Fore.WHITE +
          "\tEx: 'C:\\NSLS_2data\\1D'"
          "\n\nNote: if directory does not exist, click folder icon on top right of prompt to create a directory"
          "\n\tPress 'Enter' when done writing directory name\n")
    oneDdir = tkfilebrowser.askopendirname(initialdir=main_dir,
                                           title="Select / create directory for integrated (1D) patterns")
    if not oneDdir:
        print(Fore.RED + 'Selection not valid, will auto create 1D directory in main directory\n')
    else:
        print(Fore.GREEN + 'Integrated pattern directory selected as:\n\t', str(oneDdir), '\n')
        oneDdirname = oneDdir.split(os.sep)[-1]

############################################Calibration info selection##############################################
    #.poni file select
    print(Fore.CYAN + "Please select the .poni file to be used for detector geometry (e.g., detector tilts, "
          "sample-to-detector distance)\n")
    fullponif= tkfilebrowser.askopenfilename(initialdir=main_dir,
                                             filetypes=(("poni files","*.poni"),("all files","*.*")),
                                             title="Select .poni file")
    if not fullponif:
        print(Back.RED + 'Selection cancelled, quitting program\nPlease restart\n')
        sys.exit()
    else:
        ponif = fullponif.split(os.sep)[-1]
        print(Fore.GREEN + 'poni selected:\n\t',str(ponif),'\n')
        poni_dir = fullponif.partition(ponif)[0].rsplit(os.sep,1)[0]

    #mask select
    print(Fore.CYAN + "Please select the static mask file to be used for integration\n"
                      "Press 'Cancel' for no mask\n")
    fullmaskf = tkfilebrowser.askopenfilename(initialdir=poni_dir,
                                              filetypes=(("mask files", "*.tif|*.edf|*.npy|*.msk"), ("all files",
                                                                                                          "*.*")),
                                              title="Select mask file or press 'Cancel' for no mask")
    if not fullmaskf:
        print(Fore.RED + "No mask file selected - Setting mask to 'None'\n")
        fullmaskf = None
    else:
        maskf = fullmaskf.split(os.sep)[-1]
        print(Fore.GREEN + 'mask selected:\n\t', str(maskf), '\n')
        mask_dir = fullmaskf.partition(maskf)[0].rsplit(os.sep, 1)[0]

###############################Integration prm (#radial points, int method, xunits, error model#####################
    sleep(1)
    print(Fore.GREEN + '\nSetting up parameters for integration\n\n')
    sleep(1)

    print(Fore.BLUE + '\nDefault integration parameters:', Fore.GREEN + '\n\tPixel splitting method: ', d_intmethod,
          Fore.GREEN + '\n\tX units: ', d_xunit, Fore.GREEN + '\n\tRadial (x-unit) points: ', d_rad_points, Fore.GREEN +
          '\n\tRadial (x-unit) range: ', d_rad_range, Fore.GREEN + '\n\tAzimuthal (deg.) range: ', d_azim_range,
          Fore.GREEN + '\n\tAutomask pixel value: ', d_neg_mask, Fore.GREEN + '\n\tIntensity error model: ',
          d_errormodel, '\n\n')

    intprmselect = input(Fore.YELLOW + "Would you like to use the default integration parameters above or provide"
                         " them via CLI?\n\t[1] for default\n\t[2] to provide integration parameters\n\n")

    if intprmselect == '1':
        intmethod = d_intmethod
        xunit = d_xunit
        rad_points = d_rad_points
        rad_range = d_rad_range
        azim_range = d_azim_range
        neg_mask = d_neg_mask
        errormodel = d_errormodel
    if intprmselect == '2':
        print(Fore.GREEN + '\nInput integration parameters as prompted - press Enter with no input for default'
                           ' setting\n' + Fore.WHITE)
        intmethod = input(
            Fore.YELLOW + "\nInput pixel splitting method to use (e.g., 'no', 'full', 'bbox', 'pseudo')\n" + Fore.WHITE)
        if not intmethod:
            intmethod = d_intmethod
        elif intmethod not in intmethod_accepted and intmethod.lower() not in intmethod_accepted:
            print(
                Fore.RED + "Input for pixel splitting method not accepted - must be 'no', 'full', 'bbox','pseudo'"
                           " or empty for default\nSetting to default: " + str(d_intmethod) + '\n')
            intmethod = d_intmethod
        else:
            intmethod = intmethod.lower()

        xunit = input(Fore.YELLOW + "\nInput x unit to use (e.g., '2th_deg', '2th_rad', 'q_A^-1', 'd*2_A^-2')\n\t"
                                    "Shorthand:\n\t'tth' for '2th_deg\n\t'q' for 'q_A^-1'\n" + Fore.WHITE)
        if not xunit:
            xunit = d_xunit
        elif xunit.lower() == 'tth':
            xunit = d_xunit
        elif xunit.lower() == 'q':
            xunit = 'q_A^-1'
        elif xunit not in xunit_accepted and xunit.lower() not in xunit_accepted:
            print(
                Fore.RED + "Input for x unit not accepted - must be '2th_deg', '2th_rad', 'q_nm^-1', 'q_A^-1',"
                           " 'r_mm' or empty for default\nSetting to default: " + str(d_xunit) + '\n')
            xunit = d_xunit
        else:
            xunit = xunit.lower()

        rad_points = input(Fore.YELLOW + "\nInput # radial (x) points to use for integration\n" + Fore.WHITE)
        if not rad_points:
            rad_points = d_rad_points
        else:
            rad_points = int(rad_points)  # this is done separately since an empty input causes ValueError

        rad_range = input(Fore.YELLOW + "\nInput radial (x) range values for integration as a comma-separated "
                                        "pair of start, finish values\n\tEx: 0.0,15.4\n\tFor default full range "
                                        "press Enter with no input or input 'None'\n" + Fore.WHITE)
        if not rad_range:
            rad_range = d_rad_range
        elif rad_range == 'none' or rad_range.lower() == 'none':
            rad_range = d_rad_range
        else:
            if True in [i.isdigit() for i in rad_range]:
                try:
                    rad_range = ast.literal_eval(
                        rad_range)  # this evaluates the strings and properly formats them as numbers or NoneType
                    if rad_range is not None:
                        if len(rad_range) > 1:
                            if type(rad_range[0]) != float and type(rad_range[0]) != int:
                                print(Fore.RED + 'Lower limit of rad_range set to unaccepted operand type: ' +
                                      str(type(
                                          rad_range[0])) + Fore.RED + '\nSetting rad_range to default min, max\n')
                                rad_range = d_rad_range
                            if rad_range is not None:
                                if type(rad_range[1]) != float and type(rad_range[1]) != int:
                                    print(Fore.RED + 'Upper limit of rad_range set to unaccepted operand type: ' +
                                          str(type(
                                              rad_range[
                                                  1])) + Fore.RED + '\nSetting rad_range to default min, max\n')
                                    rad_range = d_rad_range
                        elif len(rad_range) == 1:
                            print(Fore.RED + 'rad_range set to a single value, must provide a pair of values\n'
                                             'Setting rad_range to default min, max\n')
                            rad_range = d_rad_range
                except TypeError:
                    print(
                        Fore.RED + "Input for radial range not accepted - must be pair of numbers, empty, or 'None'"
                                   "\n\tSetting to default 'None' for full radial range\n")
                    rad_range = d_rad_range
            else:
                print(Fore.RED + 'rad_range set to unaccepted operand type ' + str(type(rad_range)) +
                      Fore.RED + '\nSetting rad_range to default min, max\n')
                rad_range = d_rad_range

        azim_range = input(Fore.YELLOW + "\nInput azimuthal (deg.) range values for integration as a comma-separated "
                                         "pair of start, finish values\n\tEx: 0,180\n\tFor default full range "
                                         "press Enter with no input or input 'None'\n" + Fore.WHITE)
        if not azim_range:
            azim_range = d_azim_range
        elif azim_range == 'none' or azim_range.lower() == 'none':
            azim_range = d_azim_range
        else:
            if True in [i.isdigit() for i in azim_range]:
                try:
                    azim_range = ast.literal_eval(
                        azim_range)  # this evaluates the strings and properly formats them as numbers or NoneType
                    if azim_range is not None:
                        if len(azim_range) > 1:
                            if type(azim_range[0]) != float and type(azim_range[0]) != int:
                                print(Fore.RED + 'Lower limit of azim_range set to unaccepted operand type: ' +
                                      str(type(
                                          azim_range[0])) + Fore.RED + '\nSetting azim_range to default min, max\n')
                                azim_range = d_azim_range
                            if azim_range is not None:
                                if type(azim_range[1]) != float and type(azim_range[1]) != int:
                                    print(Fore.RED + 'Upper limit of azim_range set to unaccepted operand type: ' +
                                          str(type(
                                              azim_range[
                                                  1])) + Fore.RED + '\nSetting azim_range to default min, max\n')
                                    azim_range = d_azim_range
                        elif len(azim_range) == 1:
                            print(Fore.RED + 'azim_range set to a single value, must provide a pair of values\n'
                                             'Setting azim_range to default min, max\n')
                            azim_range = d_azim_range
                except TypeError:
                    print(
                        Fore.RED + "Input for azimuthal range not accepted - must be pair of numbers, empty, or 'None'"
                                   "\n\tSetting to default 'None' for full radial range\n")
                    azim_range = d_azim_range
            else:
                print(Fore.RED + 'azim_range set to unaccepted operand type ' + str(type(azim_range)) +
                      Fore.RED + '\nSetting azim_range to default min, max\n')
                azim_range = d_azim_range

        neg_mask = input(
            Fore.YELLOW + "\nInput value for pixels to be automasked (e.g., -1e-10, 'None')\n" + Fore.WHITE)
        if not neg_mask:
            neg_mask = d_neg_mask
        elif neg_mask == 'none' or neg_mask.lower() == 'none':
            neg_mask = None
        else:
            if True in [i.isdigit() for i in neg_mask]:
                try:
                    neg_mask = ast.literal_eval(neg_mask)
                    if neg_mask is not None:
                        if type(neg_mask) == str:
                            if True in [i.isdigit() for i in neg_mask]:
                                print('Negative mask string contains a number, converting to float\n')
                                neg_mask = float(neg_mask)
                            if neg_mask != float and neg_mask != int:
                                if neg_mask in neg_mask_accepted or neg_mask.lower() in neg_mask_accepted:
                                    print(Fore.GREEN + 'Automasking turned off based on user input as ' +
                                          str(neg_mask) + '\n')
                            else:
                                print(Fore.RED + 'Automasking input is a string but does not match acceptable '
                                                 'answers\nSetting to default: ' + str(d_neg_mask) + '\n')
                                neg_mask = d_neg_mask
                        if type(neg_mask) == float or type(neg_mask) == int:
                            neg_mask = float(neg_mask)
                        else:
                            neg_mask = d_neg_mask
                            print(Fore.RED + 'Cannot convert automasking input to a number type (e.g., float, int)'
                                             '\nSetting to default: ' + str(d_neg_mask) + '\n')
                except TypeError:
                    print(Fore.RED + "Input for automasking not accepted - must be a number, 'None', or empty\n"
                                     "Setting to default: " + str(d_neg_mask) + '\n')
                    neg_mask = d_neg_mask

        errormodel = input(Fore.YELLOW + "\nInput intensity error model (e.g., 'None', 'poisson')\n"
                           + Fore.WHITE)
        if not errormodel:
            errormodel = d_errormodel
        elif type(errormodel) == str:
            if errormodel in errormodel_accepted or errormodel.lower() in errormodel_accepted:
                print(Fore.GREEN + 'Intensity error model choice accepted as: ' + errormodel + '\n')
                errormodel = errormodel.lower()
            else:
                print(Fore.RED + 'Intensity error model choice is a string but does not match acceptable answers\n'
                                 'Setting to default: ' + d_errormodel + '\n')
                errormodel = d_errormodel
        else:
            print(Fore.RED + "Intensity error model input not valid, must be 'None' or 'poisson' \n"
                             'Setting to default: ' + d_errormodel + '\n')
            errormodel = d_errormodel

        print(Fore.BLUE + '\nIntegration parameters:', Fore.GREEN + '\n\tPixel splitting method: ',intmethod,
              Fore.GREEN + '\n\tX units: ', xunit, Fore.GREEN + '\n\tRadial (x-unit) points: ', rad_points,
              Fore.GREEN + '\n\tRadial (x-unit) range: ', rad_range, Fore.GREEN + '\n\tAzimuthal (deg.) range: ',
              azim_range,Fore.GREEN + '\n\tAutomask pixel value: ', neg_mask, Fore.GREEN +
              '\n\tIntensity error model: ',errormodel, '\n\n')

        intprmconfirm = input(Fore.YELLOW + 'Are the integration parameters above correct?\n\t[1] for correct\n\t'
                                            '[2] for incorrect, redo\n\t[3] for incorrect, quit program\n')

        if intprmconfirm == '1':
            print(Fore.GREEN + '\nIntegration parameters confirmed to be correct\n')

        elif intprmconfirm == '2':
            print(Fore.GREEN + 'Input integration parameters - press Enter with no input for default setting\n'
                + Fore.WHITE)

            intmethod = input(Fore.YELLOW + "\nInput pixel splitting method to use (e.g., 'no', 'full', 'bbox', "
                                            "'pseudo')\n" + Fore.WHITE)
            if not intmethod:
                intmethod = d_intmethod
            elif intmethod not in intmethod_accepted and intmethod.lower() not in intmethod_accepted:
                print(Fore.RED + "Input for pixel splitting method not accepted - must be 'no', 'full', 'bbox',"
                               "'pseudo' or empty for default\nSetting to default: " + str(d_intmethod) + '\n')
                intmethod = d_intmethod
            else:
                intmethod = intmethod.lower()

            xunit = input(Fore.YELLOW + "\nInput x unit to use (e.g., '2th_deg', '2th_rad', 'q_A^-1', 'd*2_A^-2')\n\t"
                                        "Shorthand:\n\t'tth' for '2th_deg\n\t'q' for 'q_A^-1'\n" + Fore.WHITE)
            if not xunit:
                xunit = d_xunit
            elif xunit.lower() == 'tth':
                xunit = d_xunit
            elif xunit.lower() == 'q':
                xunit = 'q_A^-1'
            elif xunit not in xunit_accepted and xunit.lower() not in xunit_accepted:
                print(Fore.RED + "Input for x unit not accepted - must be '2th_deg', '2th_rad', 'q_nm^-1', 'q_A^-1'"
                                 ", 'r_mm' or empty for default\nSetting to default: " + str(d_xunit) + '\n')
                xunit = d_xunit
            else:
                xunit = xunit.lower()

            rad_points = input(Fore.YELLOW + "\nInput # radial (x) points to use for integration\n" + Fore.WHITE)
            if not rad_points:
                rad_points = d_rad_points
            else:
                rad_points = int(rad_points)  # this is done separately since an empty input causes ValueError

            rad_range = input(Fore.YELLOW + "\nInput radial (x) range values for integration as a comma-separated "
                                            "pair of start, finish values\n\tEx: 0.0,15.4\n\tFor default full range "
                                            "press Enter with no input or input 'None'\n" + Fore.WHITE)
            if not rad_range:
                rad_range = d_rad_range
            elif rad_range == 'none' or rad_range.lower() == 'none':
                rad_range = d_rad_range
            else:
                if True in [i.isdigit() for i in rad_range]:
                    try:
                        rad_range = ast.literal_eval(
                            rad_range)  # this evaluates the strings and properly formats them as numbers or NoneType
                        if rad_range is not None:
                            if len(rad_range) > 1:
                                if type(rad_range[0]) != float and type(rad_range[0]) != int:
                                    print(Fore.RED + 'Lower limit of rad_range set to unaccepted operand type: ' +
                                          str(type(
                                              rad_range[
                                                  0])) + Fore.RED + '\nSetting rad_range to default min, max\n')
                                    rad_range = d_rad_range
                                if rad_range is not None:
                                    if type(rad_range[1]) != float and type(rad_range[1]) != int:
                                        print(
                                            Fore.RED + 'Upper limit of rad_range set to unaccepted operand type: ' +
                                            str(type(
                                                rad_range[
                                                    1])) + Fore.RED + '\nSetting rad_range to default min, max\n')
                                        rad_range = d_rad_range
                            elif len(rad_range) == 1:
                                print(Fore.RED + 'rad_range set to a single value, must provide a pair of values\n'
                                                 'Setting rad_range to default min, max\n')
                                rad_range = d_rad_range
                    except TypeError:
                        print(
                            Fore.RED + "Input for radial range not accepted - must be pair of numbers, empty, or 'None'"
                                       "\n\tSetting to default 'None' for full radial range\n")
                        rad_range = d_rad_range
                else:
                    print(Fore.RED + 'rad_range set to unaccepted operand type ' + str(type(rad_range)) +
                          Fore.RED + '\nSetting rad_range to default min, max\n')
                    rad_range = d_rad_range

            azim_range = input(
                Fore.YELLOW + "\nInput azimuthal (deg.) range values for integration as a comma-separated "
                              "pair of start, finish values\n\tEx: 0,180\n\tFor default full range "
                              "press Enter with no input or input 'None'\n" + Fore.WHITE)
            if not azim_range:
                azim_range = d_azim_range
            elif azim_range == 'none' or azim_range.lower() == 'none':
                azim_range = d_azim_range
            else:
                if True in [i.isdigit() for i in azim_range]:
                    try:
                        azim_range = ast.literal_eval(
                            azim_range)  # this evaluates the strings and properly formats them as numbers or NoneType
                        if azim_range is not None:
                            if len(azim_range) > 1:
                                if type(azim_range[0]) != float and type(azim_range[0]) != int:
                                    print(Fore.RED + 'Lower limit of azim_range set to unaccepted operand type: ' +
                                          str(type(
                                              azim_range[
                                                  0])) + Fore.RED + '\nSetting azim_range to default min, max\n')
                                    azim_range = d_azim_range
                                if azim_range is not None:
                                    if type(azim_range[1]) != float and type(azim_range[1]) != int:
                                        print(
                                            Fore.RED + 'Upper limit of azim_range set to unaccepted operand type: ' +
                                            str(type(
                                                azim_range[
                                                    1])) + Fore.RED + '\nSetting azim_range to default min, max\n')
                                        azim_range = d_azim_range
                            elif len(azim_range) == 1:
                                print(Fore.RED + 'azim_range set to a single value, must provide a pair of values\n'
                                                 'Setting azim_range to default min, max\n')
                                azim_range = d_azim_range
                    except TypeError:
                        print(
                            Fore.RED + "Input for azimuthal range not accepted - must be pair of numbers, empty, or "
                                       "'None'\n\tSetting to default 'None' for full radial range\n")
                        azim_range = d_azim_range
                else:
                    print(Fore.RED + 'azim_range set to unaccepted operand type ' + str(type(azim_range)) +
                          Fore.RED + '\nSetting azim_range to default min, max\n')
                    azim_range = d_azim_range

            neg_mask = input(
                Fore.YELLOW + "\nInput value for pixels to be automasked (e.g., -1e-10, 'None')\n" + Fore.WHITE)
            if not neg_mask:
                neg_mask = d_neg_mask
            elif neg_mask == 'none' or neg_mask.lower() == 'none':
                neg_mask = None
            else:
                if True in [i.isdigit() for i in neg_mask]:
                    try:
                        neg_mask = ast.literal_eval(neg_mask)
                        if neg_mask is not None:
                            if type(neg_mask) == str:
                                if True in [i.isdigit() for i in neg_mask]:
                                    print('Negative mask string contains a number, converting to float\n')
                                    neg_mask = float(neg_mask)
                                if neg_mask != float and neg_mask != int:
                                    if neg_mask in neg_mask_accepted or neg_mask.lower() in neg_mask_accepted:
                                        print(
                                            Fore.GREEN + 'Automasking turned off based on user input as ' +
                                            str(neg_mask) + '\n')
                                else:
                                    print(Fore.RED + 'Automasking input is a string but does not match acceptable '
                                                     'answers\nSetting to default: ' + str(d_neg_mask) + '\n')
                                    neg_mask = d_neg_mask
                            if type(neg_mask) == float or type(neg_mask) == int:
                                neg_mask = float(neg_mask)
                            else:
                                neg_mask = d_neg_mask
                                print(
                                    Fore.RED + 'Cannot convert automasking input to a number type (e.g., float, int'
                                               ')\nSetting to default: ' + str(d_neg_mask) + '\n')
                    except TypeError:
                        print(Fore.RED + "Input for automasking not accepted - must be a number, 'None', or empty\n"
                                         "Setting to default: " + str(d_neg_mask) + '\n')
                        neg_mask = d_neg_mask

            errormodel = input(Fore.YELLOW + "\nInput intensity error model (e.g., 'None', 'poisson')"
                                             "\n" + Fore.WHITE)
            if not errormodel:
                errormodel = d_errormodel
            elif type(errormodel) == str:
                if errormodel in errormodel_accepted or errormodel.lower() in errormodel_accepted:
                    print(Fore.GREEN + 'Intensity error model choice accepted as: ' + errormodel + '\n')
                    errormodel = errormodel.lower()
                else:
                    print(Fore.RED + 'Intensity error model choice is a string but does not match acceptable '
                                     'answers\nSetting to default: ' + d_errormodel + '\n')
                    errormodel = d_errormodel
            else:
                print(Fore.RED + "Intensity error model input not valid, must be 'None' or 'poisson'"
                                 '\nSetting to default: ' + d_errormodel + '\n')
                errormodel = d_errormodel

            print(Fore.BLUE + '\nIntegration parameters:', Fore.GREEN + '\n\tPixel splitting method: ',intmethod,
                  Fore.GREEN + '\n\tX units: ', xunit, Fore.GREEN + '\n\tRadial (x-unit) points: ', rad_points,
                  Fore.GREEN + '\n\tRadial (x-unit) range: ', rad_range, Fore.GREEN + '\n\tAzimuthal (deg.) range: '
                  , azim_range,Fore.GREEN + '\n\tAutomask pixel value: ', neg_mask, Fore.GREEN +
                  '\n\tIntensity error model: ',errormodel, '\n\n')

            intprmconfirm = input(Fore.YELLOW + 'Are the integration parameters above correct?\n\t[1] for correct'
                                                '\n\t[2] for incorrect, quit program\n')
            if intprmconfirm == '1':
                print(Fore.GREEN + '\nIntegration parameters confirmed to be correct\n')
            elif intprmconfirm == '2':
                print(Back.RED + '\nQuitting program\nPlease restart\n')
                sys.exit()
        elif intprmconfirm == '3':
            print(Back.RED + '\nQuitting program\nPlease restart\n')
            sys.exit()
########################################Making 1D dirs in 1D dir########################################################
    print(Fore.WHITE + '\nCreating sub directories for integrated patterns to be saved\nDirectories with names '
                       'matching selected tiff folders will be created in integrated pattern directory provided\n')
    if oneDdir:  # first check if oneDdir was properly saved as a variable from GUI selection
        if os.path.isdir(oneDdir):
            print(Fore.GREEN + 'Directory for integrated patterns already exists\n')
        if not os.path.isdir(oneDdir):  # if directory does not exist but variable does, make dir
            try:
                os.makedirs(oneDdir, exist_ok=True)
                print(Fore.GREEN + 'Created directory for integrated patterns:\n' + Fore.WHITE + str(oneDdir)
                      + '\n')
            except NameError:
                print(Fore.RED + 'Error creating directory from provided name - using default method')
                oneDdir = None  # set as None so that following conditional is true to make default dir
    if not oneDdir:  # if a 1D directory was not selected or variable has error, make a dir
        oneDdir = main_dir + os.sep + oneDdefault

        try:
            os.makedirs(oneDdir, exist_ok=True)
            print(Fore.GREEN + 'Created default directory for integrated patterns:\n' + Fore.WHITE + str(oneDdir)
                             + '\n')
        except IsADirectoryError:
            print(Fore.GREEN + 'Directory already exists - continuing')

    if GUItiffs is False and CLItiffs is True:  # keyword based dirstoint setup
        dirstoint = []
        main, dirs, files = next(os.walk(tiff_dir))
        if keyword in keyword_all_accepted or keyword.lower() in keyword_all_accepted:
            print(Fore.GREEN + 'Based on provided keyword, all directories are selected')
            for dir in dirs:  # looping to add dirs to preserve list ordering
                dirstoint.append(dir)
        else:
            for dir in dirs:
                if keyword in dir:
                    dirstoint.append(dir)

    # Creating subdirs for each tiff folder - for GUI and CLI options
    oneD_folders = []
    missingdirs = []
    for dir in dirstoint:  # dirstoint is for GUI or CLI option
        try:
            os.mkdir(os.path.join(oneDdir, dir))
            print(Fore.GREEN + '\tCreated integrated pattern directory for: ', dir)
            oneD_folders.append(dir)  # only appends if successful
        except FileExistsError:
            print(Fore.RED + '\tIntegrated pattern directory already exists for: ', dir)
            oneD_folders.append(dir)

    # Checking that tiff and 1D directory lists match
    #if dirstoint == oneD_folders:
        #print(Fore.GREEN + '\nTiff directory list matches integrated pattern directory list\n\n')
    if dirstoint != oneD_folders:
        for i in dirstoint:
            if i not in oneD_folders:
                missingdirs.append(i)
        print(Fore.RED + 'Missing sub directories for integrated patterns:')
        print(*missingdirs, sep='\n')
        print(Back.RED + '\nTiff and integrated pattern directory lists do not match'
                         '\nQuitting program - check for errors')
        sys.exit()
##################################################User provides .int filename###########################################
    print(Fore.GREEN + '\n\nFinished setting up guided integration\nSaving integration setup as a .int file - follow '
          + 'window prompt to choose file name and location\n')
    # User creates filename but this is an empty file for now
    intfname_user = tkfilebrowser.asksaveasfilename(initialdir=main_dir,
                                                    filetypes=[("int files", "*.int")],
                                                    defaultext='.int',
                                                    title="Save .int file")
    if not intfname_user:
        print(Fore.RED + 'Filename not provided for integration (.int) file\n' + Fore.GREEN +
              'An auto named .int file will be saved in:\n\t' + Fore.WHITE + tiff_dir + '\n')
    else:
        print(Fore.GREEN + 'Integration (.int) file:\n\t' + Fore.WHITE + intfname_user.split(os.sep)[-1] + '\n')

########################################End of Guided Integration Setup#################################################

############################################Start of .int file loading##################################################
if guideduse == '2':
    #read .int file
    print(Fore.CYAN + 'Please select integration (.int) file to load\n')
    intfname_user = tkfilebrowser.askopenfilename(initialdir='',
                                                    filetypes=[("int files", "*.int")],
                                                    defaultext='.int',
                                                    title="Select .int file")
    if not intfname_user:
        print(Fore.RED + 'Selection not valid or cancelled - try again\n')
        print(Fore.CYAN + 'Please select integration (.int) file to load\n')
        intfname_user = tkfilebrowser.askopenfilename(initialdir='',
                                                    filetypes=[("int files", "*.int")],
                                                    defaultext='.int',
                                                    title="Select .int file")
        if not intfname_user:
            print(Back.RED + 'Selection not valid or cancelled\nQuitting program - please restart')
            sys.exit()
        else:
            print(Fore.GREEN + 'Integration (.int) file selected:\n\t', str(intfname_user.rsplit(os.sep)[-1]), '\n')
    else:
        print(Fore.GREEN + 'Integration (.int) file selected:\n\t', str(intfname_user.rsplit(os.sep)[-1]), '\n')

    # reading lines from .int file, creating dictionary of keywords, finding line nums, storing prms in dict
    intlines = [line for line in open(intfname_user)]
    keyworddict = {'Data from NSLS-II, APS, or SSRL': None,
                   'Main integrated pattern directory': None,
                   'Poni file': None,
                   'Mask file': None,
                   'Pixel splitting method': None,
                   'X unit': None,
                   'Radial (x-unit) points': None,
                   'Radial (x-unit) range': None,
                   'Azimuthal (deg.) range': None,
                   'Automask pixel value': None,
                   'Intensity error model': None,
                   }
    editstartstr = 'Integration parameters and setup.'
    editendstr = 'User notes / metadata allowed below here:'
    startcheck = False
    endcheck = False
    editstartnum = None
    editendnum = None

    for num, line in enumerate(intlines, 0):
        if editstartstr in line and startcheck == False:
            editstartnum = num
            startcheck = True  # stops loop on 1st instance - prevents reading through user metadata / notes
        if editendstr in line and endcheck == False:
            editendnum = num
            endcheck = True  # stops loop on 1st instance - prevents reading through user metadata / notes

    # what if the start / end text for the editing block is removed?
    if not editstartnum:
        print(Fore.RED + 'Section header for integration parameters and setup has been modified - can not identify '
                         'start of section\n')
    if not editendnum:
        print(Fore.RED + 'Section footer for integration parameters and setup has been modified - can not identify '
                         'end of section\nSetting expected section end to end of file')
        editendnum = len(intlines)

    if not editstartnum:  # without section header we need to distinguish prm description from prm declaration
        for i in keyworddict:
            element_found = False
            for num, line in enumerate(intlines, 0):
                if i in line:
                    if '#' in line:  # this is necessary because s.find(x) = -1 if x is not found
                        if line.find('#') < line.find(i):  # if '#' precedes text, we assume this is a comment
                            pass
                        elif line.find('#') > line.find(i):
                            keyworddict[i] = num
                            element_found = True
                            break
                    else:  # if only the header block is modified, but not the lines, this finds them
                        keyworddict[i] = num
                        element_found = True
                        break
                if not element_found:
                    keyworddict[i] = 'N/A'
    else:  # expect this condition to be true unless user edits section they should not
        for i in keyworddict:
            element_found = False
            for num, line in enumerate(intlines, 0):
                if editstartnum <= num <= editendnum and i in line:  # 1st instance will be in editable block
                    keyworddict[i] = num
                    element_found = True
                    break
            if not element_found:
                keyworddict[i] = 'N/A'

    # checks that all keywords are found - if not, identifies those with issues and quits
    if 'N/A' in keyworddict.values():
        print(Fore.RED + 'Issue with .int file formatting - cannot find all keyword lines for integration setup\n'
                         'The following keywords are not formatted properly:')
        for i in keyworddict:
            if keyworddict[i] == 'N/A':
                print('\t' + i)
        print('\n' + Fore.RED + 'Please resolve formatting issues in the selected .int file for the keywords above\n')
        print(Back.RED + 'Quitting program - restart when ready')
        sys.exit()

    # here we create variables from the content on lines - error checking is done next separately
    # inline comments are checked for each line and whitespace is stripped at beginning / end of strings
    synsrc = intlines[keyworddict['Data from NSLS-II, APS, or SSRL']].strip('\n').split(':')[1]
    if '#' in synsrc:
        synsrc = synsrc.split('#')[0]
    synsrc = synsrc.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    oneDdir = intlines[keyworddict['Main integrated pattern directory']].strip('\n').split('Main integrated pattern directory:')[1]  # directories and fnames split explicitly to avoid splitting paths
    if '#' in oneDdir:
        oneDdir = oneDdir.split('#')[0]
    oneDdir = oneDdir.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    fullponif = intlines[keyworddict['Poni file']].strip('\n').split('Poni file:')[1]  # directories and fnames split explicitly to avoid splitting paths
    if '#' in fullponif:
        fullponif = fullponif.split('#')[0]
    fullponif = fullponif.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    fullmaskf = intlines[keyworddict['Mask file']].strip('\n').split('Mask file:')[1]  # directories and fnames split explicitly to avoid splitting paths
    if '#' in fullmaskf:
        fullmaskf = fullmaskf.split('#')[0]
    fullmaskf = fullmaskf.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    intmethod = intlines[keyworddict['Pixel splitting method']].strip('\n').split(':')[1]
    if '#' in intmethod:
        intmethod = intmethod.split('#')[0]
    intmethod = intmethod.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    xunit = intlines[keyworddict['X unit']].strip('\n').split(':')[1]
    if '#' in xunit:
        xunit = xunit.split('#')[0]
    xunit = xunit.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    rad_points = intlines[keyworddict['Radial (x-unit) points']].strip('\n').split(':')[1]
    if '#' in rad_points:
        rad_points = rad_points.split('#')[0]
    rad_points = rad_points.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    rad_range = intlines[keyworddict['Radial (x-unit) range']].strip('\n').split(':')[1]
    if '#' in rad_range:
        rad_range = rad_range.split('#')[0]
    rad_range = rad_range.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    azim_range = intlines[keyworddict['Azimuthal (deg.) range']].strip('\n').split(':')[1]
    if '#' in azim_range:
        azim_range = azim_range.split('#')[0]
    azim_range = azim_range.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    neg_mask = intlines[keyworddict['Automask pixel value']].strip('\n').split(':')[1]
    if '#' in neg_mask:
        neg_mask = neg_mask.split('#')[0]
    neg_mask = neg_mask.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    errormodel = intlines[keyworddict['Intensity error model']].strip('\n').split(':')[1]
    if '#' in errormodel:
        errormodel = errormodel.split('#')[0]
    errormodel = errormodel.strip()  # only strips whitespace at the beginning and end - avoids stripping intentional spaces

    #check that poni file exists and is an acceptable filetype
    if os.path.isfile(fullponif) is False:
        print(Back.RED + 'Poni file provided does not exist - check both filepath and filename\nQuitting - fix errors')
        sys.exit()

    if not fullponif.endswith('.poni'):
        print(Back.RED + 'Poni file provided is not the accepted filetype - extension must be .poni'
                         '\nQuitting - fix errors')
        sys.exit()

    #check that mask file exists and is an acceptable filetype
    if os.path.isfile(fullmaskf) is False:
        print(Fore.RED + 'Mask file provided does not exist - check both filepath and filename\nNo mask will be used')
        fullmaskf = None

    if not any((fullmaskf.endswith(ext) for ext in maskfext_accepted)):
        print(Fore.RED + 'Mask file provided is an unaccepted filetype - must be .tif, .edf, .msk, or .npy'
                         '\nNo mask will be used')
        fullmaskf = None

    #error checking on int parameters
    if synsrc == 'NSLS-II' or synsrc.lower() == 'nsls-ii':
        image_extension = '.tiff'
    elif synsrc == 'APS' or synsrc == 'SSRL' or synsrc.lower() == 'aps' or synsrc.lower() == 'ssrl':
        image_extension = '.tif'
    else:
        print(Fore.RED + 'Data source not accepted - must be NSLS-II, APS, or SSRL'
                         '\nQuitting setup - please fix and restart')
        sys.exit()

    if intmethod not in intmethod_accepted and intmethod.lower() not in intmethod_accepted:
        print(Fore.RED + "Input for pixel splitting method not accepted - must be 'no', 'full', 'bbox', or 'pseudo'")

    if xunit.lower() == 'tth':
        xunit = d_xunit
    if xunit.lower() == 'q':
        xunit = 'q_A^-1'
    elif xunit not in xunit_accepted and xunit.lower() not in xunit_accepted:
        print(Fore.RED + "Input for x unit not accepted - must be '2th_deg', '2th_rad', 'q_nm^-1', 'q_A^-1', d*2_A^-2,"
                         "or 'r_mm'")
    else:
        xunit = xunit.lower()

    rad_points = int(rad_points)

    if not rad_range:
        rad_range = d_rad_range
    elif rad_range == 'none' or rad_range.lower() == 'none':
        rad_range = d_rad_range
    else:
        if True in [i.isdigit() for i in rad_range]:
            try:
                rad_range = ast.literal_eval(
                    rad_range)  # this evaluates the strings and properly formats them as numbers or NoneType
                if rad_range is not None:
                    if len(rad_range) > 1:
                        if type(rad_range[0]) != float and type(rad_range[0]) != int:
                            print(Fore.RED + 'Lower limit of rad_range set to unaccepted operand type: ' +
                                  str(type(rad_range[0])) + Fore.RED + '\nSetting rad_range to default min, max\n')
                            rad_range = d_rad_range
                        if rad_range is not None:
                            if type(rad_range[1]) != float and type(rad_range[1]) != int:
                                print(Fore.RED + 'Upper limit of rad_range set to unaccepted operand type: ' +
                                      str(type(rad_range[1])) + Fore.RED + '\nSetting rad_range to default min, max\n')
                                rad_range = d_rad_range
                    elif len(rad_range) == 1:
                        print(Fore.RED + 'rad_range set to a single value, must provide a pair of values\n'
                                         'Setting rad_range to default min, max\n')
                        rad_range = d_rad_range
            except TypeError:
                print(Fore.RED + "Input for radial range not accepted - must be pair of numbers, empty, or 'None'"
                                 "\n\tSetting to default 'None' for full radial range\n")
                rad_range = d_rad_range
        else:
            print(Fore.RED + 'rad_range set to unaccepted operand type ' + str(type(rad_range)) +
                  Fore.RED + '\nSetting rad_range to default min, max\n')
            rad_range = d_rad_range

    if not azim_range:
        azim_range = d_azim_range
    elif azim_range == 'none' or azim_range.lower() == 'none':
        azim_range = d_azim_range
    else:
        if True in [i.isdigit() for i in azim_range]:
            try:
                azim_range = ast.literal_eval(
                    azim_range)  # this evaluates the strings and properly formats them as numbers or NoneType
                if azim_range is not None:
                    if len(azim_range) > 1:
                        if type(azim_range[0]) != float and type(azim_range[0]) != int:
                            print(Fore.RED + 'Lower limit of azim_range set to unaccepted operand type: ' +
                                  str(type(azim_range[0])) + Fore.RED + '\nSetting azim_range to default min, max\n')
                            azim_range = d_azim_range
                        if azim_range is not None:
                            if type(azim_range[1]) != float and type(azim_range[1]) != int:
                                print(Fore.RED + 'Upper limit of azim_range set to unaccepted operand type: ' +
                                      str(type(azim_range[1])) + Fore.RED + '\nSetting azim_range to default min, max\n')
                                azim_range = d_azim_range
                    elif len(azim_range) == 1:
                        print(Fore.RED + 'azim_range set to a single value, must provide a pair of values\n'
                                         'Setting azim_range to default min, max\n')
                        azim_range = d_azim_range
            except TypeError:
                print(Fore.RED + "Input for azimuthal range not accepted - must be pair of numbers, empty, or 'None'"
                                 "\n\tSetting to default 'None' for full radial range\n")
                azim_range = d_azim_range
        else:
            print(Fore.RED + 'azim_range set to unaccepted operand type ' + str(type(azim_range)) +
                  Fore.RED + '\nSetting azim_range to default min, max\n')
            azim_range = d_azim_range

    if not neg_mask:
        neg_mask = d_neg_mask
    elif neg_mask == 'none' or neg_mask.lower() == 'none':
        neg_mask = None
    else:
        if True in [i.isdigit() for i in neg_mask]:
            try:
                neg_mask = ast.literal_eval(neg_mask)
                if neg_mask is not None:
                    if type(neg_mask) == str:
                        if True in [i.isdigit() for i in neg_mask]:
                            print('Negative mask string contains a number, converting to float\n')
                            neg_mask = float(neg_mask)
                        if neg_mask != float and neg_mask != int:
                            if neg_mask in neg_mask_accepted or neg_mask.lower() in neg_mask_accepted:
                                print(Fore.GREEN + 'Automasking turned off based on user input as ' +
                                      str(neg_mask) + '\n')
                        else:
                            print(Fore.RED + 'Automasking input is a string but does not match acceptable '
                                             'answers\nSetting to default: ' + str(d_neg_mask) + '\n')
                            neg_mask = d_neg_mask
                    if type(neg_mask) == float or type(neg_mask) == int:
                        neg_mask = float(neg_mask)
                    else:
                        neg_mask = d_neg_mask
                        print(Fore.RED + 'Cannot convert automasking input to a number type (e.g., float, int)'
                                         '\nSetting to default: ' + str(d_neg_mask) + '\n')
            except TypeError:
                print(Fore.RED + "Input for automasking not accepted - must be a number, 'None', or empty\n"
                                 "Setting to default: " + str(d_neg_mask) + '\n')
                neg_mask = d_neg_mask

    if not errormodel:
        errormodel = d_errormodel
    elif type(errormodel) == str:
        if errormodel in errormodel_accepted or errormodel.lower() in errormodel_accepted:
            print(Fore.GREEN + 'Intensity error model choice accepted as: ' + errormodel + '\n')
            errormodel = errormodel.lower()
        else:
            print(Fore.RED + 'Intensity error model choice is a string but does not match acceptable answers\n'
                             'Setting to default: ' + d_errormodel + '\n')
            errormodel = d_errormodel
    else:
        print(Fore.RED + "Intensity error model input not valid, must be 'None' or 'poisson' \n"
                         'Setting to default: ' + d_errormodel + '\n')
        errormodel = d_errormodel
    ####################################### tiff selection (GUI / CLI) #################################################
    tiffselect = input(Fore.YELLOW + "\nWould you like to select directories to integrate via a GUI file browser\nor "
                                     "through a command line interface (keyword-based)?\n\t[1] for GUI selection "
                                     "tool\n\t[2] for command line interface (keyword-based)\n")
    # GUI tiff selection
    if tiffselect == "1":
        print(Fore.CYAN + "\nPlease select the folders that you would like to integrate.\nNote: for NSLS-II select the "
                          "parent directories to 'dark_sub'\n")
        fulldirstoint = tkfilebrowser.askopendirnames(initialdir='', title="Select folders to integrate")
        if not fulldirstoint:
            print(Back.RED + 'Selection cancelled, quitting program\nPlease restart\n')
            sys.exit()
        else:
            dirstoint = []
            for dir in fulldirstoint:  # This loop makes a list with just the folder names, not full paths
                f = dir.split(os.sep)[-1]
                dirstoint.append(f)

            if len(dirstoint) == 1:
                print(Fore.GREEN + '\nFolder selected to integrate:')
                for f in dirstoint:
                    print('\t' + f)

            elif len(dirstoint) > 1:
                print(Fore.GREEN + '\n' + str(len(dirstoint)) + ' folders selected to integrate:')
                for f in dirstoint:
                    print('\t' + f)
            GUItiffs = True
            CLItiffs = False
        tiff_dir = fulldirstoint[0].partition(dirstoint[0])[0].rsplit(os.sep, 1)[0]
        main_dir = tiff_dir.rsplit(os.sep, 1)[0]
        print(Fore.GREEN + '\nMain directory:\n\t' + Fore.WHITE + main_dir + Fore.GREEN + '\nTiff directory:\n\t'
              + Fore.WHITE + tiff_dir + '\n')

    # CLI tiff selection based on keyword
    elif tiffselect == "2":
        # First we need to pick the directory where folders containing tiffs are
        print(Fore.CYAN + "\nPlease select the directory that contains folders with images to integrate"
              + Fore.WHITE + "\nExample:\n\tParent tiff directory = 'C:\\User\\Data\\BeamlineExperiment1\\tiff_base'"
                             "\n\tFolder to integrate = 'C:\\User\\Data\\BeamlineExperiment1\\tiff_base\\Sample1'\n")
        tiff_dir = tkfilebrowser.askopendirname(initialdir='',
                                                title="Select parent tiff directory - see prompt for examples")
        if not tiff_dir:
            print(Back.RED + 'Selection cancelled, quitting program\nPlease restart\n')
            sys.exit()
        else:
            main_dir = tiff_dir.rsplit(os.sep, 1)[0]
            print(Fore.GREEN + 'Main tiff directory selected:\n\t' + Fore.WHITE + tiff_dir + '\n')
            print(Fore.GREEN + 'Main directory:\n\t' + Fore.WHITE + main_dir + '\n')
        # Next we accept the keyword
        keyword = input(Fore.YELLOW + "What keyword is present in the folder names containing files you would like"
                                      " to integrate?\n\tEx: 'LiCl' is a keyword for 'Fe3LiCl_100Cannealed'\n\tNote: "
                                      "enter 'ALL' to select all sub-directories containing images to integrate\n")
        print('\nThe keyword is: ', keyword)
        keywordcorrect = input(Fore.YELLOW + "\nIs the keyword correct?\n\t[1] for correct\n\t[2] for incorrect, redo"
                                             "\n\t[3] for incorrect, quit program\n")
        if keywordcorrect == '1':
            print(Fore.GREEN + 'Keyword confirmed to be correct\n')
            GUItiffs = False
            CLItiffs = True
        if keywordcorrect == '2':
            keyword = input(Fore.YELLOW + "What keyword is present in the folder names containing files you would "
                                          "like to integrate?\n\tEx: 'LiCl' is a keyword for 'Fe3LiCl_100Cannealed'"
                                          "\n\tNote: enter 'ALL' to select all sub-directories containing images to"
                                          " integrate\n")
            print('\nThe keyword is: ', keyword)
            keywordcorrect = input(Fore.YELLOW + "\nIs the keyword correct?\n\t[1] for correct\n\t[2] for incorrect, "
                                                 "quit program\n")
            if keywordcorrect == '1':
                print(Fore.GREEN + 'Keyword confirmed to be correct\n')
                GUItiffs = False
                CLItiffs = True
            if keywordcorrect == '2':
                print(Back.RED + 'Quitting program\nPlease restart\n')
                sys.exit()
        if keywordcorrect == '3':
            print(Back.RED + 'Quitting program\nPlease restart\n')
            sys.exit()
    elif tiffselect != '1' and tiffselect != '2':
        print(Back.RED + 'Invalid input - quitting program\nPlease restart\n')
        sys.exit()

    ########################################## directory creation ######################################################
    print(Fore.WHITE + '\nCreating sub directories for integrated patterns to be saved\nDirectories with names '
                       'matching selected tiff folders will be created in integrated pattern directory provided\n')
    if oneDdir:  # first check if oneDdir was properly saved as a variable from GUI selection
        if os.path.isdir(oneDdir):
            print(Fore.GREEN + 'Directory for integrated patterns already exists\n')
        if not os.path.isdir(oneDdir):  # if directory does not exist but variable does, make dir
            try:
                os.makedirs(oneDdir, exist_ok=True)
                print(Fore.GREEN + 'Created directory for integrated patterns:\n' + Fore.WHITE + str(oneDdir)
                      + '\n')
            except NameError:
                print(Fore.RED + 'Error creating directory from provided name - using default method')
                oneDdir = None  # set as None so that following conditional is true to make default dir
    if not oneDdir:  # if a 1D directory was not selected or variable has error, make a dir
        oneDdir = main_dir + os.sep + oneDdefault
        try:
            os.makedirs(oneDdir, exist_ok=True)
            print(Fore.GREEN + 'Created default directory for integrated patterns:\n' + Fore.WHITE + str(oneDdir)
                  + '\n')
        except IsADirectoryError:
            print(Fore.GREEN + 'Directory already exists - continuing')

    if GUItiffs is False and CLItiffs is True:  # keyword based dirstoint setup
        dirstoint = []
        main, dirs, files = next(os.walk(tiff_dir))
        if keyword in keyword_all_accepted or keyword.lower() in keyword_all_accepted:
            print(Fore.GREEN + 'Based on provided keyword, all directories are selected')
            for dir in dirs:  # looping to add dirs to preserve list ordering
                dirstoint.append(dir)
        else:
            for dir in dirs:
                if keyword in dir:
                    dirstoint.append(dir)

    # Creating subdirs for each tiff folder - for GUI and CLI options
    oneD_folders = []
    missingdirs = []
    for dir in dirstoint:  # dirstoint is for GUI or CLI option
        try:
            os.mkdir(os.path.join(oneDdir, dir))
            print(Fore.GREEN + '\tCreated integrated pattern directory for: ', dir)
            oneD_folders.append(dir)  # only appends if successful
        except FileExistsError:
            print(Fore.RED + '\tIntegrated pattern directory already exists for: ', dir)
            oneD_folders.append(dir)

    # Checking that tiff and 1D directory lists match
    # if dirstoint == oneD_folders:
    # print(Fore.GREEN + '\nTiff directory list matches integrated pattern directory list\n\n')
    if dirstoint != oneD_folders:
        for i in dirstoint:
            if i not in oneD_folders:
                missingdirs.append(i)
        print(Fore.RED + 'Missing sub directories for integrated patterns:')
        print(*missingdirs, sep='\n')
        print(Back.RED + '\nTiff and integrated pattern directory lists do not match'
                         '\nQuitting program - check for errors')
        sys.exit()

########################################################################################################################
#####Both guided integration and .int file loading proceed from here - final prm confirm, file saving, integration######
########################################################################################################################

###########################################CONFIRMATION BEFORE INTEGRATION BEGINS#######################################
print(Fore.BLUE + '\n\nData source, directories, .poni and mask files:', Fore.GREEN +
          '\n\tData from NSLS-II, APS, or SSRL: ', synsrc, Fore.GREEN + '\n\tMain integrated pattern directory: ',
          oneDdir, Fore.GREEN + '\n\tPoni file: ', fullponif, Fore.GREEN + '\n\tMask file: ', fullmaskf)
print(Fore.BLUE + '\nIntegration parameters:', Fore.GREEN + '\n\tPixel splitting method: ', intmethod,
      Fore.GREEN + '\n\tX units: ', xunit, Fore.GREEN + '\n\tRadial (x-unit) points: ', rad_points, Fore.GREEN +
      '\n\tRadial (x-unit) range: ', rad_range, Fore.GREEN + '\n\tAzimuthal (deg.) range: ', azim_range,
      Fore.GREEN + '\n\tAutomask pixel value: ', neg_mask, Fore.GREEN + '\n\tIntensity error model: ',
      errormodel, '\n')
print(Fore.BLUE + 'Directories to be parsed for images to integrate:')
for i in dirstoint:  # lazy way of doing this without tabs is: print(*dirstoint, sep='\n')
    print('\t' + i)
start_int = input(Fore.YELLOW + '\nAre both the integration parameters and list of directories above correct?' +
                  '\n\t[1] for yes (proceeds with integration) *if an .int file was loaded, it will be overwritten*' +
                  '\n\t[2] for no (quits program - edit .int manually for loading or redo guided integration)\n')
#################################Save .int file before processing start_int input#######################################
# info to be stored in file and filename
dtobj = datetime.now(tz=None)
datestr = dtobj.strftime("%d%b%Y")
timestr = dtobj.strftime("%H-%M-%S")
datetimestr = dtobj.strftime("%d%b%Y_%H-%M-%S")

intfname = 'GuidedIntegration_' + datetimestr + '.int'  # default .int filename
recfname = 'GuidedIntegration_' + datetimestr + '_record.txt'  # default record filename - currently not customizable

# text to write to .int and record files
GI_statement = ''.join(['\n#Date: ', datestr,
                        '\n#Time: ', timestr,
                        '\n#Version: ', Version,
                        '\n#Github: github.com/adamcorrao/GuidedIntegration'
                        '\n#Citation: Guided Integration Version ', str(Version), ' (',
                        str(dtobj.strftime("%Y")),
                        '). https://github.com/adamcorrao/GuidedIntegration',
                        '\n#Citation for latest paper on pyFAI: Kieffer, J., Valls, V., Blanc, N. & Hennig, C. (2020). '
                        'J. Synchrotron Rad. 27, 558-566.'])
# description of int prms and directory setup
desc_statement = ''.join([
    '\n\n#Description of parameters, options available, acceptable operand / filetypes (Guided Integration formats this correctly):',
    "\n\t#Data from NSLS-II, APS, or SSRL: where was data collected? Expected image extensions are .tiff for NSLS-II and .tif for APS / SSRL. NSLS-II images expected in sub directory 'dark_sub'",
    '\n\t#Main integrated pattern directory: directory where sub directories are created in which integrated patterns are saved',
    '\n\t#Poni file: instrument geometry (e.g., sample-to-detector distance, detector tilts) file - filetype must be .poni',
    '\n\t#Mask file: static mask (e.g., beamstop, detector edges) - must be one of the following filetypes: *.tif | *.edf | *.npy | *.msk',
    '\n\n#Integration parameters (see pyFAI docs for more details):',
    '\n\t#Pixel splitting options: no (no splitting), full (full splitting), bbox (bounding box), pseudo (scaled down bbox)',
    '\n\t#X unit options: 2th_deg, 2th_rad, q_nm^-1, q_A^-1, d*2_A^-2, r_mm',
    '\n\t#Radial (x-unit) points: the number of bins in the x-axis - must be a number',
    '\n\t#Radial (x-unit) range: radial range to integrate image over (x-unit specific) - must be a pair of comma separated numbers or None for full range',
    '\n\t#Azimuthal (deg.) range: azimuthal (deg.) range to integrate image over - must be a pair of comma separated numbers or None for full range',
    '\n\t#Automask pixel value: pixels with intensity less than this value are automatically masked - must be a number',
    '\n\t#Intensity error model options: none, poisson for variance = I'
])
# directories, calib / poni
int_setup_statement = ''.join([
    '\n\n', str('#' * 150),
    '\nIntegration parameters and setup.\nBelow here user can edit parameters after the colon. ',
    'In-line comments are allowed.\n',
    str('#' * 150),
    '\n\nData from NSLS-II, APS, or SSRL: ', str(synsrc),
    '\nMain integrated pattern directory: ', str(oneDdir),
    '\nPoni file: ', str(fullponif),
    '\nMask file: ', str(fullmaskf)])
intprm_statement = ''.join(['\n\nPixel splitting method: ', str(intmethod),
                            '\nX unit: ', str(xunit),
                            '\nRadial (x-unit) points: ', str(rad_points),
                            '\nRadial (x-unit) range: ', str(rad_range),
                            '\nAzimuthal (deg.) range: ', str(azim_range),
                            '\nAutomask pixel value: ', str(neg_mask),
                            '\nIntensity error model: ', str(errormodel),
                            ])
usernotes_statement = ''.join(['\n\n', str('#' * 150),
                               '\nUser notes / metadata allowed below here:\n',
                               str('#' * 150)])

if not intfname_user:
    intfdir = tiff_dir  # default saves the .int file in tiff_dir (parent to directories containing images)
else:
    intfname = intfname_user.split(os.sep)[-1]
    intfdir = intfname_user.rsplit(os.sep, 1)[0]  # avoids conditional for user-defined name vs. default

with open(intfdir + os.sep + intfname, 'a+') as f:
    f.seek(0)  # a+ mode is read/write starting at end of file, this moves to the beginning
    f.truncate()  # deletes everything below current cursor position (which we set to 0)
    f.write('#Guided Integration .int parameter file')
    f.write(GI_statement)
    f.write(desc_statement)
    f.write(int_setup_statement)
    f.write(intprm_statement)
    f.write(usernotes_statement)

# processing confirmation (yes / no) from start_int prompt
if not start_int:
    print(Back.RED + 'No acceptable user input\nProgram quit - edit .int manually or redo guided integration\n')
    sys.exit()
if start_int != '1':
    print(Back.RED + 'Program quit - edit .int manually or redo guided integration\n')
    sys.exit()

print(Fore.GREEN + 'Proceeding with integration\n\n')
#####################################################INTEGRATION########################################################
ai = pyFAI.load(fullponif)
if fullmaskf is not None:
    static_mask = fabio.open(fullmaskf).data

totalintcount = 0
numtiffdirs = len(dirstoint)  # number of total directories to integrate
intedimages = []  # list to append integrated image names to

# evaulate total num. files to integrate up front for progress and time estimation
numtiffstoint = 0
for fold in (dirstoint):
    if synsrc == 'NSLS-II':  # consider evaluating outside loop
        int_dir = tiff_dir + os.sep + fold + os.sep + 'dark_sub' + os.sep  # for NSLS-II / xpdacq file paths
    elif synsrc == 'APS' or synsrc == 'SSRL':  # consider evaluating outside loop
        int_dir = tiff_dir + os.sep + fold + os.sep  # for APS / SSRL file paths
    ftoint = [f for f in os.listdir(int_dir) if f.endswith(image_extension)]
    numtiffstoint += len(ftoint)

if errormodel == 'None' or errormodel == 'none' or errormodel is None:
    oneD_extension = '.xy'
    oneD_columns = ['#' + str(xunit), 'I']
elif errormodel == 'poisson': #or errormodel == 'azimuthal':
    oneD_extension = '.xye'
    oneD_columns = ['#' + str(xunit), 'I', 'I_err']

if numtiffdirs == 1:
    with tqdm(total=numtiffstoint, desc=(Fore.CYAN + ' Total progress: '), dynamic_ncols=True,
              unit='image', bar_format="{l_bar}{bar} [ time left: {remaining} ]") as pbar:
        for fold in dirstoint:
            sleep(.01)
            if synsrc == 'NSLS-II':  # consider evaluating outside loop
                int_dir = tiff_dir + os.sep + fold + os.sep + 'dark_sub' + os.sep  # for NSLS-II / xpdacq file paths
            elif synsrc == 'APS' or synsrc == 'SSRL':  # consider evaluating outside loop
                int_dir = tiff_dir + os.sep + fold + os.sep  # for APS / SSRL file paths
            ftoint = [f for f in os.listdir(int_dir) if
                      f.endswith(image_extension)]  # files to integrate in selected dirs
            oneD_toplace = oneDdir + os.sep + fold + os.sep  # 1D directory to save 1D patterns to
            for file in ftoint:
                sleep(0.01)
                totalintcount += 1
                darksub_img = fabio.open(int_dir + file).data
                oneD_name = oneD_toplace + os.sep + file.strip(image_extension) + oneD_extension
                ai.integrate1d(data=darksub_img, mask=static_mask, dummy=neg_mask, method=intmethod,
                               npt=rad_points, azimuth_range=azim_range, radial_range=rad_range,
                               error_model=errormodel, filename=oneD_name, correctSolidAngle=False,
                               unit=xunit)
                oneD_f = pd.read_csv(oneD_name, skiprows=d_lines2skip, delim_whitespace=True, header=None)
                oneD_f.columns = oneD_columns
                oneD_f.to_csv(oneD_name, index=False, float_format='%.8f', sep='\t')
                intedimages.append(file)
                pbar.update()
    pbar.close()

else:
    with tqdm(total=numtiffstoint, desc=(Fore.CYAN + ' Total progress: '), dynamic_ncols=True, position=1,
              unit='image', bar_format="{l_bar}{bar} [ time left: {remaining} ]") as pbar:
        for fold in dirstoint:
            sleep(.01)
            if synsrc == 'NSLS-II':  # consider evaluating outside loop
                int_dir = tiff_dir + os.sep + fold + os.sep + 'dark_sub' + os.sep  # for NSLS-II / xpdacq file paths
            elif synsrc == 'APS' or synsrc == 'SSRL':  # consider evaluating outside loop
                int_dir = tiff_dir + os.sep + fold + os.sep  # for APS / SSRL file paths
            ftoint = [f for f in os.listdir(int_dir) if
                      f.endswith(image_extension)]  # files to integrate in selected dirs
            oneD_toplace = oneDdir + os.sep + fold + os.sep  # 1D directory to save 1D patterns to
            for file in tqdm(ftoint, desc=(Fore.GREEN + ' ' + fold + ' progress: '), position=0, leave=True,
                             unit='image', dynamic_ncols=True):
                sleep(0.01)
                totalintcount += 1
                darksub_img = fabio.open(int_dir + file).data
                oneD_name = oneD_toplace + os.sep + file.strip(image_extension) + oneD_extension
                ai.integrate1d(data=darksub_img, mask=static_mask, dummy=neg_mask, method=intmethod,
                               npt=rad_points, azimuth_range=azim_range, radial_range=rad_range,
                               error_model=errormodel, filename=oneD_name, correctSolidAngle=False,
                               unit=xunit)
                oneD_f = pd.read_csv(oneD_name, skiprows=d_lines2skip, delim_whitespace=True, header=None)
                oneD_f.columns = oneD_columns
                oneD_f.to_csv(oneD_name, index=False, float_format='%.8f', sep='\t')
                intedimages.append(file)
                pbar.update()
    pbar.close()

print(Fore.GREEN + '\nTotal number of files integrated: ', str(totalintcount))

###############################################Writing record file######################################################
with open(intfdir + os.sep + recfname, 'a+') as rec:
    rec.seek(0)
    rec.truncate()
    rec.seek(0)
    rec.write('#Guided Integration record file')
    rec.write(GI_statement)
    rec.write(int_setup_statement)
    rec.write(intprm_statement)
    rec.write(''.join(['\n\n', str('#' * 150),
                       '\nIntegration record\n',
                       str('#' * 150), '\n\nDirectories parsed for files to integrate:\n']))
    rec.write('\n'.join(dirstoint))
    rec.write('\n\nImages integrated:\n')
    rec.write('\n'.join(intedimages))
    rec.write(usernotes_statement)
print(Fore.GREEN + 'Integration record file saved: ' + Fore.WHITE + str(recfname))
print(Fore.GREEN + 'Done')
