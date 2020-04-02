### TRS Image

Convert a modern image file (jpg, png, etc) into a TRS80 BASIC program to reproduce the image on a TRS80 (low-res, black and white).  

Allows for source image pan, zoom, and output image contrast adjustment.  

Written as an entry into Dusty's www.trs-80.org.uk 2018 Competition: **HI-RES-LO**

Target is a TRS80 Model III, LDOS 5.3.1, and Misosys LBASIC.

## Version History
- v1.5
 - Added (I)nvert colors option
 - Added .tim (TRS Image file) output file for use with TRS-80 Screen Designer (TSD)
 - See www.plaidvest.com
- v1.4 
 - Cross platform version
 - GUI = Tk/Tcl
 - Increase performance when adjusting contrast
- v1.3
 - Separate PC and Mac versions
 - PC version uses command line parameters (no file open/save dialog boxes)
 - GUI = wxPython

## Setup Instructions

**Requirements**:

* Python 3 (www.python.org)
* Pillow 5.2.0 (pip install Pillow)

### Mac
Run from the terminal:

1. cd /folder/to/trsimage
1. ./trs_image.py

### PC
Run from the command prompt:

1. cd c:\folder\to\trsimage
1. python trs_image.py

---

## TRS80 Instructions to run BASIC programs

Using the TRS Image BASIC output file(s):

* Copy BASIC program to a virtual .dsk image (I use TRS Tools)  
-or-  
* Copy to actual diskette using your favorite method

1. Boot TRS80 Model III with LDOS 5
2. Switch to Misosys LBasic by typing BASIC <Enter>
3. Load sample program: LOAD "xxx.BAS"
4. Run sample program: RUN
5. (Optional) Re-run with RUN or save the smaller program back to disk SAVE "xxx.BAS"
6. Return to LDOS with CMD"S"

