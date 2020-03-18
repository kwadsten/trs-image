#!/usr/bin/env python3

#
# TRS Image
#
# Convert a modern image file (jpg, png, etc) into a TRS80 BASIC program
# to reproduce the image on a TRS80 (low-res, black and white).
#
# Allows for source image pan, zoom, and output image contrast adjustment.
#
# Written as an entry into Dusty's www.trs-80.org.uk 2018 Competition: HI-RES-LO
#
# Target is a TRS80 Model III, LDOS 5.3.1, and Misosys LBASIC.
#
# NOTE:  The BASIC program that is generated uses a TRS80 "string packing" technique.
#        After the BASIC program is run on a TRS80 for the first time it will delete
#        the logic and DATA statements used to build the packed strings.  This reduces
#        the program size (6K -> 3.5K).
#        The user can then re-save the program back to disk to save disk space.
#
# Requires: python 3, Pillow
#
#   pip install Pillow
#
# Version 1.5
# 03/16/2020
#
# By Kyle Wadsten
# kwadsten@comcast.net
#

#TODO: fix movement rate when zoomed in/out

from tkinter import *
from tkinter import messagebox
from tkinter import filedialog

from PIL import ImageTk, ImageDraw
import PIL.Image

import os.path
import json
import collections


Size = collections.namedtuple('Size', 'width height')
Point = collections.namedtuple('Point', 'x y')


class g:
    """
    Global variables
    """
    VERSION = 1.5

    BASIC_CURR_LINE_NB = None

    BLIT_TEXT_POS = None
    BLIT_COLOR = None

    # Fonts
    FONT_SMALL = "Courier -16"
    FONT_BIG = "Ariel -20 bold"

    # Actual TRS80 screen specs
    TRS_ACTUAL_SCREEN_SIZE = Size(128, 48)

    DISPLAY_SEPARATOR_WIDTH = 20        # space between src and trs displays
    INSTRUCTION_SEPARATOR_WIDTH = 60    # space between image displays and text area
    INSTRUCTION_AREA_HEIGHT = 220       # height of text area

    # Contrast is the tolerance for determing black or white pixel.
    # 128 is average.  User can change with keyboard.
    # Compare to source image average pixel color (R+G+B/3) to determine black/white on TRS80
    DEFAULT_CONTRAST = 60
    MIN_CONTRAST = 0
    MAX_CONTRAST = 100
    CONTRAST_RATE = 2
    CONTRAST_ACCELERATOR = 5
    CONTRAST = DEFAULT_CONTRAST

    REDRAW_ALL = 0
    REDRAW_CONTRAST = 1

    # Source image movement
    MOVE_ACCELERATOR = 7
    MOVE_RATE = None

    # Source Image zoom
    DEFAULT_ZOOM = 0
    MIN_ZOOM = -50
    MAX_ZOOM = 50
    ZOOM_RATE = 1
    ZOOM_ACCELERATOR = 2
    ZOOM = DEFAULT_ZOOM

    # Colors
    COLOR_WHITE = 'white'
    COLOR_BLACK = 'black'
    COLOR_GREY = 'gray'
    RGB_BLACK = (0, 0, 0)
    RGB_WHITE = (255, 255, 255)
    
    BG_COLOR_RGB = [RGB_BLACK, RGB_WHITE]
    FG_COLOR = [COLOR_WHITE, COLOR_BLACK]

    # Virtual TRS80 screen specs (for sample image display)
    TRS_VIRTUAL_PIXEL_SIZE = Size(4, 8)
    TRS_VIRTUAL_SCREEN_SIZE = Size(TRS_ACTUAL_SCREEN_SIZE.width * TRS_VIRTUAL_PIXEL_SIZE.width,
                                   TRS_ACTUAL_SCREEN_SIZE.height * TRS_VIRTUAL_PIXEL_SIZE.height)
    TRS_VIRTUAL_SCREEN_RATIO = TRS_VIRTUAL_SCREEN_SIZE.width / TRS_VIRTUAL_SCREEN_SIZE.height

    TRS_VIRTUAL_PIXEL_WHITE = PIL.Image.new('RGB', TRS_VIRTUAL_PIXEL_SIZE, COLOR_WHITE)

    # Source image display size (based on virtual trs pixel size to maintain aspect ratio)
    IMG_DISPLAY_SIZE = TRS_VIRTUAL_SCREEN_SIZE

    # App screen is twice as wide as display windows + some seperator space
    SCREEN_SIZE = Size((IMG_DISPLAY_SIZE.width * 2) + DISPLAY_SEPARATOR_WIDTH + 14,
                        IMG_DISPLAY_SIZE.height + INSTRUCTION_AREA_HEIGHT)

    # Where to show images/text
    IMG_DISPLAY_LOC = Point(10, 10)
    TRS_DISPLAY_LOC = Point(IMG_DISPLAY_SIZE.width + DISPLAY_SEPARATOR_WIDTH + 10, 10)
    TEXT_DISPLAY_LOC = Point(0, IMG_DISPLAY_SIZE.height + INSTRUCTION_SEPARATOR_WIDTH)
    INPUT_FILE_DISPLAY_LOC = Point(IMG_DISPLAY_LOC.x + 5, IMG_DISPLAY_LOC.y + IMG_DISPLAY_SIZE.height + 5)

    # Bitmaps
    src_original_img = None     # Original image
    src_original_size = None

    src_stretched_img = None    # Original image in VIRTUAL TRS aspect ratio
    src_stretched_size = None
    src_stretched_margin = None

    src_display_img = None      # Source image to display (viewport of src_stretched)
    src_display_pi = None       # Source image to display (canvas PhotoImage)

    viewport_origin = None      # Position of viewport into src_stretched_bmp.  Changes with move and zoom.
    viewport_size = None        # Size of viewport.  Changes with zoom.

    trs_actual_img = None       # TRS image with 1x1 pixels (for output)
    trs_display_img = None      # TRS image for display (virtual pixel size)
    trs_display_pi = None       # TRS image for display (canvas PhotoImage)

    input_uri = ''              # Input source image path
    output_bas_uri = ''         # Output BASIC file path
    output_tim_uri = ''         # Output TIM file path (for import into TRS-80 Screen Designer)

    CONFIG_FILE = 'config.ini'
    CONFIG_FOLDERS = ['', '']   # 0=input, 1=output

    canvas = None
    src_pixel_color_data = None
    inverted_image = False
    color_index = 0            # default = normal colors.  1 = inverted colors

def init(root):
    """
    Initialize canvas (main window)
    """

    root.resizable(False, False)  # Prevent X,Y resizing
    root.title('TRS Image v' + str(g.VERSION))

    g.canvas = Canvas(root, width=g.SCREEN_SIZE.width, height=g.SCREEN_SIZE.height)
    g.canvas.pack()

    g.src_display_img = PIL.Image.new('RGB', g.IMG_DISPLAY_SIZE, color='white')
    g.trs_display_img = PIL.Image.new('RGB', g.TRS_VIRTUAL_SCREEN_SIZE, color='white')

    g.src_display_pi = ImageTk.PhotoImage(g.src_display_img)
    g.trs_display_pi = ImageTk.PhotoImage(g.trs_display_img)

    g.canvas.create_image(g.IMG_DISPLAY_LOC.x, g.IMG_DISPLAY_LOC.y, image=g.src_display_pi, anchor=NW)
    g.canvas.create_image(g.TRS_DISPLAY_LOC.x, g.TRS_DISPLAY_LOC.y, image=g.trs_display_pi, anchor=NW)

    root.bind('<Key>', key_down)

    read_config_file()

    redraw()

def key_down(event):
    """
    Handle keyboard events
    :param event: EVT_KEY_DOWN
    :return:
    """
    # Only need to redraw screen when user adjusts image position, size, or contrast
    redraw_flag = False

    key = event.keysym
    key_lower = key.lower()
    shift = True if event.state & 1 else False

    # Handle keyboard exceptions
    if key == 'underscore':
        key = 'minus'
        shift = True

    if key == 'equals':
        key = 'plus'
        shift = False

    # Quit program
    if key_lower == 'q':
        if g.input_uri != '' and g.output_bas_uri == '':
            messagebox.askquestion('Confirm Quit', 'Quit without generating output files?', icon='warning')
            if 'yes':
                root.quit()
        else:
            root.quit()

    # Open file
    if key_lower == 'o':
        open_file()
        redraw_flag = True

    # About box
    if key == 'a':
        messagebox.showinfo('About', 'TRS Image v' + str(g.VERSION) + '\nBy Kyle Wadsten\n2020')
        g.canvas.focus_force()

    # No image adjustments allowed until image is loaded
    if g.input_uri != '':

        # Position
        if key == 'Left':
            move_image(g.MOVE_RATE, 0, shift)
            redraw_flag = True
        if key == 'Right':
            move_image(g.MOVE_RATE * -1, 0, shift)
            redraw_flag = True
        if key == 'Up':
            move_image(0, g.MOVE_RATE * -1, shift)
            redraw_flag = True
        if key == 'Down':
            move_image(0, g.MOVE_RATE, shift)
            redraw_flag = True

        # Contrast
        if key == 'Prior':
            update_contrast(g.CONTRAST_RATE, shift)
            redraw(g.REDRAW_CONTRAST)
        if key == 'Next':
            update_contrast(g.CONTRAST_RATE * -1, shift)
            redraw(g.REDRAW_CONTRAST)

        # Zoom
        if key == 'minus':
            zoom_image(-1, shift)
            redraw_flag = True
        if key == 'plus':
            zoom_image(1, shift)
            redraw_flag = True

        # Reset image size, position, and contrast
        if key_lower == 'r':
            reset()
            redraw_flag = True

        # Invert image
        if key_lower == 'i':
            g.color_index = 1 - g.color_index    # invert color index 0/1
            g.inverted_image = not g.inverted_image
            redraw_flag = True

        # Generate BASIC output file
        if key_lower == 'g':
            generate_bas_output_file()
            generate_tim_output_file()
            redraw_flag = True

        # Regenerate source and trs images
        if redraw_flag:
            redraw()

def generate_bas_output_file():
    """
    Output a BASIC program for TRS80 that will recreate the image.
    Uses TRS80 'String Packing' logic.
    Currently is LDOS LBASIC compatible.
    User selects output directory using a standard Folder Selection Dialog.
    Output folder is saved in a config.ini file in the program directory.
    :return:
    """
    g.BASIC_CURR_LINE_NB = 0

    file_dir = filedialog.askdirectory(parent=root, initialdir=g.CONFIG_FOLDERS[1], title='Choose output directory')
    g.canvas.focus_force()
    if file_dir is None:
        return  # the user changed their mind

    # save output folder to config file
    g.CONFIG_FOLDERS[1] = file_dir
    update_config_file()

    path, filename = os.path.split(g.input_uri)
    basename = os.path.splitext(filename)[0]
    cleanname = ''.join(filter(str.isalnum, basename))[:8].upper()
    g.output_bas_uri = os.path.join(file_dir, cleanname + ".BAS")
    g.output_tim_uri = os.path.join(file_dir, basename + ".tim")

    try:
        with open(g.output_bas_uri, 'w') as f:

            write_basic_line(f, 'CLS')

            write_basic_line(f, 'PRINT"***************************************************************"')
            write_basic_line(f, 'PRINT"*                        TRS IMAGE                            *"')
            write_basic_line(f, 'PRINT"***************************************************************"')
            write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '..."')
            write_basic_line(f, 'CLEAR 1024')
            write_basic_line(f, 'A$="' + '.' * 128 + '"')
            write_basic_line(f, 'B$="' + '.' * 128 + '"')
            write_basic_line(f, 'C$="' + '.' * 128 + '"')
            write_basic_line(f, 'D$="' + '.' * 128 + '"')
            write_basic_line(f, 'E$="' + '.' * 128 + '"')
            write_basic_line(f, 'F$="' + '.' * 128 + '"')
            write_basic_line(f, 'G$="' + '.' * 128 + '"')
            write_basic_line(f, 'H$="' + '.' * 128 + '"')
            write_basic_line(f, 'D1 = 1')

            data_start_line = g.BASIC_CURR_LINE_NB
            generate_basic_data_statements(f)

            write_basic_line(f, 'X=PEEK(VARPTR(A$)+2)*256+PEEK(VARPTR(A$)+1)')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (20%)"')
            write_basic_line(f, 'X=PEEK(VARPTR(B$)+2)*256+PEEK(VARPTR(B$)+1)')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'X=PEEK(VARPTR(C$)+2)*256+PEEK(VARPTR(C$)+1)')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (40%)"')
            write_basic_line(f, 'X=PEEK(VARPTR(D$)+2)*256+PEEK(VARPTR(D$)+1)')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'X=PEEK(VARPTR(E$)+2)*256+PEEK(VARPTR(E$)+1)')
            write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (60%)"')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'X=PEEK(VARPTR(F$)+2)*256+PEEK(VARPTR(F$)+1)')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (80%)"')
            write_basic_line(f, 'X=PEEK(VARPTR(G$)+2)*256+PEEK(VARPTR(G$)+1)')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'X=PEEK(VARPTR(H$)+2)*256+PEEK(VARPTR(H$)+1)')
            write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
            write_basic_line(f, 'CLS')

            data_end_line = g.BASIC_CURR_LINE_NB
            write_basic_line(f, 'PRINT @0,   A$')
            write_basic_line(f, 'PRINT @128, B$')
            write_basic_line(f, 'PRINT @256, C$')
            write_basic_line(f, 'PRINT @384, D$')
            write_basic_line(f, 'PRINT @512, E$')
            write_basic_line(f, 'PRINT @640, F$')
            write_basic_line(f, 'PRINT @768, G$')
            write_basic_line(f, 'PRINT @896, LEFT$(H$, 127);')

            inkey_line = g.BASIC_CURR_LINE_NB
            write_basic_line(f, 'K$=INKEY$:IF K$="" GOTO ' + str(inkey_line + 10))
            write_basic_line(f, 'CLS')
            write_basic_line(f, 'PRINT"**********************************************************"')
            write_basic_line(f, 'PRINT"* IMAGE GENERATED WITH \'TRS IMAGE\' BY KYLE WADSTEN, 2018 *"')
            write_basic_line(f, 'PRINT"**********************************************************"')
            write_basic_line(f, 'PRINT""')
            write_basic_line(f, 'IF D1 = 0 THEN END')
            write_basic_line(f, 'PRINT "THE IMAGE DATA USED BY THIS PROGRAM HAS BEEN COMPRESSED."')
            write_basic_line(f, 'PRINT "YOU MAY RE-SAVE THIS PROGRAM TO CONSERVE DISK SPACE"')
            write_basic_line(f, 'PRINT "BY RUNNING THIS COMMAND: SAVE" CHR$(34) "' + cleanname + '/BAS" CHR$(34)')
            write_basic_line(f, 'IF D1 = 1 THEN DELETE ' + str(data_start_line) + '-' + str(data_end_line))
            write_basic_line(f, 'END')

    except IOError as e:
        messagebox.showerror('Error', f'Error saving data to: {g.output_bas_uri}')


def generate_tim_output_file():
    """
    Generate TRS80 image file (.tim) for input into TRS-80 Screen Designer
        by looping through each destination TRS pixel location
        and converting each pixel to a 0 or 1
    Output file already set by open basic file routine
    :return:
    """
    
    try:
        with open(g.output_tim_uri, 'w') as f:
            output_line = ''
            
            for y in range(0, g.TRS_ACTUAL_SCREEN_SIZE.height):
                for x in range(0, g.TRS_ACTUAL_SCREEN_SIZE.width):
                    # pixel_color = 0 = black, 1 = white
                    # trs normal colors: 1=on (white), 0=off (black)
                    pixel_color = rgb_to_bit(g.trs_actual_img, Point(x, y))
                    output_color = 1 - pixel_color
                    output_line += str("X" if output_color == 1 else " ")
                    
                f.write(output_line + '\n')
                output_line = ''
        
    except IOError as e:
        messagebox.showerror('Error', f'Error saving data to: {g.output_tim_uri}')

def generate_basic_data_statements(file):
    """
    Generate TRS80 BASIC DATA statements by looping through each destination TRS pixel location
    and converting bits to an 8-bit character value (128-255)
    :param file: BASIC output file handle
    :return:
    """

    # TRS80 String Packing Technique
    #
    # 2x3 "text semigraphics"
    #
    # b0 b1
    # b2 b3
    # b4 b5
    #
    # 1 0 b5 b4 b3 b2 b1 b0 = character value

    byte_cnt = 0
    data_vals = ''

    # Note: first time through, a new data line will be created
    for y in range(1, g.TRS_ACTUAL_SCREEN_SIZE.height + 1, 3):     # step 3
        for x in range(1, g.TRS_ACTUAL_SCREEN_SIZE.width + 1, 2):  # step 2
            trs_loc = Point(x, y)

            b0 = rgb_to_bit(g.trs_actual_img, Point(trs_loc.x - 1, trs_loc.y - 1))
            b1 = rgb_to_bit(g.trs_actual_img, Point(trs_loc.x - 1 + 1, trs_loc.y - 1))
            b2 = rgb_to_bit(g.trs_actual_img, Point(trs_loc.x - 1, trs_loc.y - 1 + 1))
            b3 = rgb_to_bit(g.trs_actual_img, Point(trs_loc.x - 1 + 1, trs_loc.y - 1 + 1))
            b4 = rgb_to_bit(g.trs_actual_img, Point(trs_loc.x - 1, trs_loc.y - 1 + 2))
            b5 = rgb_to_bit(g.trs_actual_img, Point(trs_loc.x - 1 + 1, trs_loc.y - 1 + 2))

            byte = 128 + (b5 << 5) + (b4 << 4) + (b3 << 3) + (b2 << 2) + (b1 << 1) + b0

            data_vals += str(byte) + ','
            byte_cnt += 1

            if byte_cnt == 50:
                data_vals = data_vals[:-1]  # remove trailing comma
                write_basic_line(file, 'DATA ' + data_vals)
                byte_cnt = 0
                data_vals = ''

    # Output final line, if necessary
    if len(data_vals) != 0:
        data_vals = data_vals[:-1]  # remove trailing comma
        write_basic_line(file, 'DATA ' + data_vals)

def write_basic_line(file, txt):
    """
    Write a single line to the TRS80 BASIC output file.
    Increments global line number before writing line.
    Prefixes output text with current line number.
    :param file: output file handle
    :param txt: basic language text line to write
    :return: Line number just written
    """
    g.BASIC_CURR_LINE_NB += 10
    file.write(str(g.BASIC_CURR_LINE_NB) + ' ' + txt + '\r\n')

def rgb_to_bit(img: Image, loc: Point):
    """
    Examine RGB color and return 1 for White and 0 for Black
    Used to build 1-bit color surface that represents TRS80 screen
    :param img: Source image
    :param loc: Pixel location
    :return: 1 (black pixel) or 0 (white pixel)
    """
    return 1 if img.getpixel(loc) == g.RGB_WHITE else 0

def draw_instructions():
    """
    Draw instructions on the application window (keyboard commands, etc.)
    :param: dc: DC to draw text onR
    :return:
    """
    if g.input_uri != '':
        blit_text(f'  Input: {g.input_uri}', font=g.FONT_SMALL, color=g.COLOR_WHITE, pos=g.INPUT_FILE_DISPLAY_LOC)
        blit_text(f' Output: {g.output_bas_uri}', font=g.FONT_SMALL, color=g.COLOR_WHITE)

    blit_text('Arrows = Move Image', pos=Point(g.TEXT_DISPLAY_LOC.x + 50, g.TEXT_DISPLAY_LOC.y + 10)
                   )
    blit_text('+/- = Adjust Zoom')
    blit_text('Page Up/Page Down = Adjust Contrast')
    blit_text('Shift = Accelerate other keys')
    blit_text('R = Reset')

    blit_text('O = Open Image File', pos=Point(g.TEXT_DISPLAY_LOC.x + 440, g.TEXT_DISPLAY_LOC.y + 10))
    if g.input_uri != '':
        blit_text('G = Generate Output Files')
    else:
        blit_text()

    blit_text()
    blit_text('A = About')
    blit_text('Q = Quit program')

    blit_text(f'Zoom = {g.ZOOM}', pos=Point(g.TEXT_DISPLAY_LOC.x + 750, g.TEXT_DISPLAY_LOC.y + 10))
    blit_text(f'Contrast = {g.CONTRAST}')
    blit_text(f'I = Invert Colors')

def blit_text(txt=' ', font=g.FONT_BIG, color=g.COLOR_BLACK, pos=None):
    """
    Common routine to draw text on the screen.
    Updates global text position BLIT_TEXT_POS
    :param txt:
    :param font:
    :param color:
    :param pos:
    :return:
    """
    if pos is None:
        pos = g.BLIT_TEXT_POS

    canvas_text = g.canvas.create_text(pos.x, pos.y, anchor=NW, text=txt, font=font, fill=color)
    x, y , x1, y1 = g.canvas.bbox(canvas_text)
    g.BLIT_TEXT_POS = Point(pos.x, (pos.y + (y1 - y) + 2))

def open_file():
    """
    Open an image using standard File Open Dialog.
    Input folder is saved in a config.ini file in the program directory.
    :return:
    """
    image_path = filedialog.askopenfilename(initialdir=g.CONFIG_FOLDERS[0],
                                            title="Select file",
                                            filetypes=(("jpeg files", "*.jpg"), ("all files", "*.*")))
    g.canvas.focus_force()
    if image_path is None:
       return  # the user changed their mind

    # Save path to config file
    g.CONFIG_FOLDERS[0] = os.path.dirname(image_path)
    update_config_file()

    # Load the image into bitmap
    try:
        g.src_original_img = PIL.Image.open(image_path)
    except IOError:
        messagebox.showerror('Error', f'Error opening {image_path}')
        return

    orig_w, orig_h = g.src_original_img.size

    # Resize image to match virtual trs image proportions by increasing
    #   height or width.  Compute position where image will be placed.
    if (orig_w / orig_h) > g.TRS_VIRTUAL_SCREEN_RATIO:
        # Landscape
        w = orig_w
        h = int(w / g.TRS_VIRTUAL_SCREEN_RATIO)
        x = 0
        y = int((h - orig_h) / 2.0)    # should be negative
    else:
        # Portrait
        h = orig_h
        w = int(h * g.TRS_VIRTUAL_SCREEN_RATIO)
        x = int((w - orig_w) / 2.0)    # should be negative
        y = 0

    # Save margins to limit movement to visible area
    g.src_stretched_margin = Size(x * -1, y * -1)

    # Resize image in-place by adding white border
    g.src_stretched_img = PIL.Image.new('RGB', (w, h), g.COLOR_WHITE)
    g.src_stretched_img.paste(g.src_original_img, (x, y))
    g.src_stretched_size = Size(w, h)

    # Set/reset default values
    g.MOVE_RATE = int(g.src_stretched_size.width / 40.0)
    g.input_uri = image_path
    reset()

def redraw(scope=g.REDRAW_ALL):
    """
    Build source and trs display images and draw to application screen
    :return:
    """
    # Draw application screen
    # First, fill with black, then draw grey rectangle for text area
    if scope != g.REDRAW_CONTRAST:
        g.canvas.delete("all")

    g.canvas.config(background="black")
    g.canvas.create_rectangle(0, g.TEXT_DISPLAY_LOC.y, g.SCREEN_SIZE.width+3, g.SCREEN_SIZE.height+3, fill=g.COLOR_GREY)

    # Draw text instructions on screen
    draw_instructions()

    if g.input_uri == '':
        return

    # Update src image if necessary
    if scope != g.REDRAW_CONTRAST:
        build_src_bitmap()
        g.canvas.create_image(g.IMG_DISPLAY_LOC, image=g.src_display_pi, anchor=NW)

    # Update trs image
    build_trs_bitmaps(scope)
    g.canvas.create_image(g.TRS_DISPLAY_LOC, image=g.trs_display_pi, anchor=NW)

def build_src_bitmap():
    """
    Copy/resize source image viewport into src display image
    :return:
    """
    # copy viewport area into new image
    viewport_img = PIL.Image.new('RGB', g.viewport_size, g.RGB_WHITE)
    viewport_img.paste(g.src_stretched_img, (-g.viewport_origin.x, -g.viewport_origin.y))
    viewport_img = viewport_img.resize(g.IMG_DISPLAY_SIZE)

    g.src_display_img = viewport_img
    g.src_display_pi = ImageTk.PhotoImage(g.src_display_img)

def build_trs_bitmaps(scope):
    """
    Build TRS bitmaps (actual and display) using the src_display bitmap
    :return:
    """
    
    g.trs_actual_img = PIL.Image.new('RGB', g.TRS_ACTUAL_SCREEN_SIZE, g.BG_COLOR_RGB[g.color_index])
    actual_draw = ImageDraw.Draw(g.trs_actual_img)
    actual_pixels_to_draw = []

    g.trs_display_img = PIL.Image.new('RGB', g.TRS_VIRTUAL_SCREEN_SIZE, g.BG_COLOR_RGB[g.color_index])
    display_draw = ImageDraw.Draw(g.trs_display_img)

    # Peformance - Compute average pixel colors if necessary
    # Not necessary to recompute if just doing a contrast adjustment
    if scope != g.REDRAW_CONTRAST:
        # compute average pixel color by averaging all src pixels of TRS pixel size
        compute_src_pixel_color_data()

    # Determine which TRS pixels need to be 'ON' (white) by inspecting source display image
    for y in range(g.TRS_ACTUAL_SCREEN_SIZE.height):
        for x in range(g.TRS_ACTUAL_SCREEN_SIZE.width):

            # compute average pixel color by averaging all src pixels of TRS pixel size
            # image backgrounds are black, so only need to draw white pixels
            if g.src_pixel_color_data[x][y] > 255 * (g.CONTRAST * .01):
                # TRS pixel is white
                # performance - build list of actual trs image pixels to draw (1x1 pixel size)
                actual_pixels_to_draw.append((x, y))

                # draw virtual trs image pixel (virtual pixel size)
                x1 = x * g.TRS_VIRTUAL_PIXEL_SIZE.width
                y1 = y * g.TRS_VIRTUAL_PIXEL_SIZE.height
                x2 = x1 + g.TRS_VIRTUAL_PIXEL_SIZE.width
                y2 = y1 + g.TRS_VIRTUAL_PIXEL_SIZE.height

                display_draw.rectangle([x1, y1, x2, y2], fill=g.FG_COLOR[g.color_index], outline=g.FG_COLOR[g.color_index])

    # draw actual trs image pixels
    actual_draw.point(actual_pixels_to_draw, fill=g.FG_COLOR[g.color_index])
    g.trs_display_pi = ImageTk.PhotoImage(g.trs_display_img)

def compute_src_pixel_color_data():
    """
    Compute average color for each src image pixel area that is equal to each TRS virtual pixel.
    Save in global so that if user adjusts contrast it doesn't need to be re-computed.
    """
    g.src_pixel_color_data = [[0 for x in range(g.TRS_ACTUAL_SCREEN_SIZE.height)]
                                  for y in range(g.TRS_ACTUAL_SCREEN_SIZE.width)]
    src_img_data = list(g.src_display_img.getdata())

    for trs_y in range(g.TRS_ACTUAL_SCREEN_SIZE.height):
        for trs_x in range(g.TRS_ACTUAL_SCREEN_SIZE.width):
            start = (trs_y * g.TRS_VIRTUAL_SCREEN_SIZE.width * g.TRS_VIRTUAL_PIXEL_SIZE.height) \
                  + (trs_x * g.TRS_VIRTUAL_PIXEL_SIZE.width)
            avg_val = 0
            cnt = 0

            for y in range(g.TRS_VIRTUAL_PIXEL_SIZE.height):
                for x in range(g.TRS_VIRTUAL_PIXEL_SIZE.width):
                    location = start + (y * g.TRS_VIRTUAL_SCREEN_SIZE.width) + x
                    red = src_img_data[location][0]
                    green = src_img_data[location][1]
                    blue = src_img_data[location][2]
                    avg_val += (red + green + blue) / 3.0
                    cnt += 1
            g.src_pixel_color_data[trs_x][trs_y] = (avg_val / cnt)

def move_image(dx, dy, shift):
    """
    Handle user source image position adjustment (viewport_origin)
    :param dx: delta x position
    :param dy: delta y position
    :param shift: shift key status (True = shift is down)
    :return:
    """
    if shift:
        dx *= g.MOVE_ACCELERATOR
        dy *= g.MOVE_ACCELERATOR

    newx = g.viewport_origin.x + dx
    newy = g.viewport_origin.y + dy

    size_w, size_h = g.src_stretched_size
    margin_w, margin_h = g.src_stretched_margin

    x_max = size_w + margin_w - g.MOVE_RATE
    x_min = (-1 * g.viewport_size.width) - margin_w + g.MOVE_RATE

    y_max = size_h + margin_h - g.MOVE_RATE
    y_min = (-1 * size_h) - margin_h + g.MOVE_RATE

    if newx < x_min:
        newx = x_min
    if newx > x_max:
        newx = x_max

    if newy < y_min:
        newy = y_min
    if newy > y_max:
        newy = y_max

    g.viewport_origin = Point(int(newx), int(newy))

def zoom_image(dx, shift):
    """
    Handle user zoom adjustment
    :param dx: zoom adjustment amount (+ or -)
    :param shift: shift key status (True = shift is down)
    :return:
    """
    if shift:
        dx *= g.ZOOM_ACCELERATOR

    prev_zoom = g.ZOOM

    g.ZOOM += dx * g.ZOOM_RATE

    if g.ZOOM < g.MIN_ZOOM:
        g.ZOOM = g.MIN_ZOOM

    if g.ZOOM > g.MAX_ZOOM:
        g.ZOOM = g.MAX_ZOOM

    # Determine how much the zoom has changed
    # Adjust current view position by this amount
    # This will prevent the display from shifting when user zooms
    delta_zoom = (g.ZOOM / 10.0) - (prev_zoom / 10.0)

    w, h = g.viewport_size

    new_viewport_width = w - (w * delta_zoom)
    new_viewport_height = h - (h * delta_zoom)

    adj_x = (w * delta_zoom) / 2.0
    adj_y = (h * delta_zoom) / 2.0
    new_x = g.viewport_origin.x + adj_x
    new_y = g.viewport_origin.y + adj_y

    g.viewport_origin = Point(int(new_x), int(new_y))
    g.viewport_size = Size(int(new_viewport_width), int(new_viewport_height))

def update_contrast(dx, shift):
    """
    Handle user contrast adjustment
    :param dx: contrast adjustment amount (+ or -)
    :param shift: shift key status (True = shift is down)
    :return:
    """

    if shift:
        dx *= g.CONTRAST_ACCELERATOR

    g.CONTRAST += dx

    if g.CONTRAST < g.MIN_CONTRAST:
        g.CONTRAST = g.MIN_CONTRAST
        return

    if g.CONTRAST > g.MAX_CONTRAST - g.CONTRAST_RATE:
        g.CONTRAST = g.MAX_CONTRAST
        return

def reset():
    """
    Reset view settings to default values
    :return:
    """
    g.viewport_origin = Point(0, 0)
    g.viewport_size = g.src_stretched_size
    g.CONTRAST = g.DEFAULT_CONTRAST
    g.ZOOM = g.DEFAULT_ZOOM
    g.output_bas_uri = ''
    g.output_tim_uri = ''

def read_config_file():
    """
    Read or create config.ini file to store input/output folders
    :return:
    """
    try:
        if os.path.isfile(g.CONFIG_FILE):
            # Read config file to get input/output folders
            with open(g.CONFIG_FILE, 'r') as f:
                g.CONFIG_FOLDERS = json.load(f)
    except IOError as e:
        messagebox.showerror('Error', 'Error reading config file')

def update_config_file():
    """
    Update config file with input/output folders
    :return:
    """
    # Read config file to get input/output folders
    try:
        with open(g.CONFIG_FILE, 'w+') as f:
            json.dump(g.CONFIG_FOLDERS, f)
    except IOError as e:
        messagebox.showerror('Error', 'Error updating config file')

# --------------------------------------------
# Main logic
# --------------------------------------------
root = Tk()
init(root)
root.mainloop()