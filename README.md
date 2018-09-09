### TRS Image

Convert a modern image file (jpg, png, etc) into a TRS80 BASIC program to reproduce the image on a TRS80 (low-res, black and white).  

Allows for source image pan, zoom, and output image contrast adjustment.  

Written as an entry into Dusty's www.trs-80.org.uk 2018 Competition: **HI-RES-LO**

Target is a TRS80 Model III, LDOS 5.3.1, and Misosys LBASIC.

## Setup Instructions

### Mac (Latest version - File Open/Save Dialog Boxes)
trs\_image_mac.py

**Requirements**:

* Python 3 (www.python.org)
* wxpython 4.0.3 (pip install wxPython)

Run from the terminal:

1. cd /folder/to/trsimage
2. ./trs_image_mac.py

---

### PC and Mac (Deprecated version - Command line input/output filenames)
trs\_image_pc.py

**Requirements**:

* Python 3 (www.python.org)
* (PC) Microsoft Visual C++ 2015 Runtime [link](https://www.microsoft.com/en-us/download/details.aspx?id=53587)
* (PC) pip (for easy install of pygame) [link](https://pip.pypa.io/en/stable/installing/)
* PyGame 1.9.4 (pip install Pygame)

Run from the command prompt:

1. cd \folder\to\trsimage
1. python trs_image_pc.py path-to-image-file path-to-output-file

**Example:**  python trs_image.py c:/images/a.jpg c:/images/a.bas

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

