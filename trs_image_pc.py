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
# python 3
# pip install pygame (v1.9.4)
#
# Version 1.0
# 08/29/2018
#
# By Kyle Wadsten
# kwadsten@comcast.net
#

import os.path
from collections import namedtuple
import sys

# Suppress pygame startup message
sys.stdout = open('/dev/null', 'w')
import pygame
sys.stdout = sys.__stdout__

VERSION = 1.0
BASIC_CURR_LINE_NB = None

FONT_SMALL = None
FONT_BIG = None

error_msg = None

# Named tuples (access values by name)
Point = namedtuple('Point', 'x y')
Size = namedtuple('Size', 'w h')

BLIT_TEXT_POS = None
BLIT_COLOR = None

# Actual TRS80 screen specs
TRS_ACTUAL_SCREEN_SIZE = Size(128, 48)

# Add 20 to width to allow for seperator
# Add 100 to height to allow for instructions
DISPLAY_SEPARATOR_WIDTH = 20
INSTRUCTION_SEPARATOR_WIDTH = 25
INSTRUCTION_AREA_HEIGHT = 160

# Contrast is the tolerance for determing black or white pixel.
# 128 is average.  User can change with keyboard.
# Compare to source image average pixel color (R+G+B/3) to determine black/white on TRS80
DEFAULT_CONTRAST = 70
MIN_CONTRAST = 1
MAX_CONTRAST = 100
CONTRAST_RATE = 2
CONTRAST_ACCELERATOR = 10
CONTRAST = DEFAULT_CONTRAST

# Source image movement
MOVE_ACCELERATOR = 7

# Source Image zoom
DEFAULT_ZOOM = 0
MIN_ZOOM = -30
MAX_ZOOM = +30
ZOOM_RATE = 1
ZOOM_ACCELERATOR = 2
ZOOM = DEFAULT_ZOOM

# Colors
COLOR_WHITE = pygame.Color('white')
COLOR_BLACK = pygame.Color('black')
COLOR_GRAY = pygame.Color('gray')

# Virtual TRS80 screen specs (for sample image display)
TRS_VIRTUAL_PIXEL_SIZE = Size(4, 8)
TRS_VIRTUAL_SCREEN_SIZE = Size(TRS_ACTUAL_SCREEN_SIZE.w * TRS_VIRTUAL_PIXEL_SIZE.w,
                               TRS_ACTUAL_SCREEN_SIZE.h * TRS_VIRTUAL_PIXEL_SIZE.h)
TRS_VIRTUAL_SCREEN_RATIO = TRS_VIRTUAL_SCREEN_SIZE.w / TRS_VIRTUAL_SCREEN_SIZE.h

TRS_VIRTUAL_PIXEL_WHITE = pygame.Surface(TRS_VIRTUAL_PIXEL_SIZE)
TRS_VIRTUAL_PIXEL_WHITE.fill(COLOR_WHITE)

TRS_VIRTUAL_PIXEL_BLACK = pygame.Surface(TRS_VIRTUAL_PIXEL_SIZE)
TRS_VIRTUAL_PIXEL_BLACK.fill(COLOR_BLACK)

# Source image display size (based on virtual trs pixel size to maintain aspect ratio)
IMG_DISPLAY_SIZE = TRS_VIRTUAL_SCREEN_SIZE

# App screen is twice as wide as display windows + some seperator space
SCREEN_SIZE = Size((IMG_DISPLAY_SIZE.w * 2) + DISPLAY_SEPARATOR_WIDTH, IMG_DISPLAY_SIZE.h + INSTRUCTION_AREA_HEIGHT)

IMG_DISPLAY_LOC = Point(0, 0)  # upper left
TRS_DISPLAY_LOC = Point(IMG_DISPLAY_SIZE.w + DISPLAY_SEPARATOR_WIDTH, 0)
TEXT_DISPLAY_LOC = Point(0, IMG_DISPLAY_SIZE.h + INSTRUCTION_SEPARATOR_WIDTH)

INPUT_FILE_LOC = Point(IMG_DISPLAY_LOC.x + 5, IMG_DISPLAY_LOC.y + IMG_DISPLAY_SIZE.h + 5)
OUTPUT_FILE_LOC = Point(TRS_DISPLAY_LOC.x + 5, TRS_DISPLAY_LOC.y + TRS_VIRTUAL_SCREEN_SIZE.h + 5)

# Surfaces
screen_surface = pygame.display.set_mode(SCREEN_SIZE)
trs_actual_surface = pygame.Surface(TRS_ACTUAL_SCREEN_SIZE)
trs_display_surface = pygame.Surface(TRS_VIRTUAL_SCREEN_SIZE)
img_display_surface = pygame.Surface(IMG_DISPLAY_SIZE)
orig_img_surface = None
work_img_surface = None

orig_view_pos = None
curr_view_pos = None

new_image = None
move_rate = None

input_uri = None
output_uri = None
generated_uri = None


def check_arguments():
    """
    Validate command line arguments (input image filename, output basic filename)
    :return:
    """

    global input_uri
    global output_uri

    # Expect image filename as an argument
    if len(sys.argv) < 3:
        print('Missing arguments.')
        print(f'Usage: {os.path.split(sys.argv[0])[1]} input_image_file output_basic_file')
        sys.exit(1)

    # Filenames (path + name)
    input_uri  = sys.argv[1]
    output_uri = sys.argv[2]

    if not os.path.isfile(input_uri):
        print(f'Image file not found: {input_uri}')
        sys.exit(1)

def open_image_file():
    """
    Open source image file
    :return: True for succcess, else False
    """
    global new_image
    global orig_img_surface
    global input_uri
    global output_uri
    global error_msg

    # NOTE: Should have an input_uri at this point.
    # If user canceled file open dialog it should
    #   contain previous filename.
    # orig_img_surface = pygame.image.load(input_uri).convert()
    # new_image = True

    try:
        error_msg = None
        orig_img_surface = pygame.image.load(input_uri).convert()
        reset()
        new_image = True
    except (IOError, pygame.error) as err:
        error_msg = f'Invalid image file. Error: {err}'
        return False

    redraw()

    return True

def display_error(msg):
    """
    Display an error message in the source image area of the screen
    :param msg:
    :return:
    """

    blit_text(msg, pos=Point(100,100))

def write_basic(f, txt):
    """
    Write a line to the TRS80 BASIC output file.
    Prefixes output text with a generated line number.
    :param f: output file handle
    :param txt: basic language text line to write
    :return:
    """

    global BASIC_CURR_LINE_NB

    BASIC_CURR_LINE_NB += 10

    f.write(str(BASIC_CURR_LINE_NB) + ' ' + txt + '\r\n')

    return BASIC_CURR_LINE_NB

def generate_basic_file():
    """
    Generate output BASIC program for TRS80 using string packing of src image.
    Currently is LDOS LBASIC compatible.
    :return: n/a
    """
    global BASIC_CURR_LINE_NB
    global generated_uri
    global output_uri

    BASIC_CURR_LINE_NB = 0

    filepath, filename = os.path.split(output_uri)
    basename = os.path.splitext(filename)[0]
    cleanname = ''.join(filter(str.isalnum, basename))[:8].upper()
    generated_uri = os.path.join(filepath, cleanname + ".BAS")

    # Create output directory if it doesn't exist
    try:
        os.makedirs(os.path.dirname(generated_uri), exist_ok=True)
    except IOError:
        print(f'Unable to create output directory: {filepath}')
        sys.exit(1)

    with open(generated_uri, 'w') as f:
        write_basic(f, 'CLS')

        write_basic(f, 'PRINT"***************************************************************"')
        write_basic(f, 'PRINT"*                 2018 HI-RES-LO COMPETITION                  *"')
        write_basic(f, 'PRINT"***************************************************************"')

        write_basic(f, 'PRINT @467, "LOADING ' + cleanname + '..."')
        write_basic(f, 'CLEAR 1024')

        write_basic(f, 'A$="' + '.' * 128 + '"')
        write_basic(f, 'B$="' + '.' * 128 + '"')
        write_basic(f, 'C$="' + '.' * 128 + '"')
        write_basic(f, 'D$="' + '.' * 128 + '"')
        write_basic(f, 'E$="' + '.' * 128 + '"')
        write_basic(f, 'F$="' + '.' * 128 + '"')
        write_basic(f, 'G$="' + '.' * 128 + '"')
        write_basic(f, 'H$="' + '.' * 128 + '"')
        data_start_line = write_basic(f, 'D1 = 1')
        generate_trs_img_data_statements(f)

        write_basic(f, 'X=PEEK(VARPTR(A$)+2)*256+PEEK(VARPTR(A$)+1)')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
        write_basic(f, 'PRINT @467, "LOADING ' + cleanname + '... (20%)"')
        write_basic(f, 'X=PEEK(VARPTR(B$)+2)*256+PEEK(VARPTR(B$)+1)')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
        write_basic(f, 'X=PEEK(VARPTR(C$)+2)*256+PEEK(VARPTR(C$)+1)')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
        write_basic(f, 'PRINT @467, "LOADING ' + cleanname + '... (40%)"')
        write_basic(f, 'X=PEEK(VARPTR(D$)+2)*256+PEEK(VARPTR(D$)+1)')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
        write_basic(f, 'X=PEEK(VARPTR(E$)+2)*256+PEEK(VARPTR(E$)+1)')
        write_basic(f, 'PRINT @467, "LOADING ' + cleanname + '... (60%)"')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
        write_basic(f, 'X=PEEK(VARPTR(F$)+2)*256+PEEK(VARPTR(F$)+1)')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
        write_basic(f, 'PRINT @467, "LOADING ' + cleanname + '... (80%)"')
        write_basic(f, 'X=PEEK(VARPTR(G$)+2)*256+PEEK(VARPTR(G$)+1)')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
        write_basic(f, 'X=PEEK(VARPTR(H$)+2)*256+PEEK(VARPTR(H$)+1)')
        write_basic(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')

        data_end_line = write_basic(f, 'CLS')
        write_basic(f, 'PRINT @0,   A$')
        write_basic(f, 'PRINT @128, B$')
        write_basic(f, 'PRINT @256, C$')
        write_basic(f, 'PRINT @384, D$')
        write_basic(f, 'PRINT @512, E$')
        write_basic(f, 'PRINT @640, F$')
        write_basic(f, 'PRINT @768, G$')
        inkey_line = write_basic(f, 'PRINT @896, LEFT$(H$, 127);')

        write_basic(f, 'K$=INKEY$:IF K$="" GOTO ' + str(inkey_line + 10))

        write_basic(f, 'CLS')
        write_basic(f, 'PRINT"**********************************************************"')
        write_basic(f, 'PRINT"* IMAGE GENERATED WITH \'TRS IMAGE\' BY KYLE WADSTEN, 2018 *"')
        write_basic(f, 'PRINT"**********************************************************"')
        write_basic(f, 'PRINT""')

        write_basic(f, 'IF D1 = 0 THEN END')
        write_basic(f, 'PRINT "THE IMAGE DATA USED BY THIS PROGRAM HAS BEEN COMPRESSED."')
        write_basic(f, 'PRINT "YOU MAY RE-SAVE THIS PROGRAM TO CONSERVE DISK SPACE"')
        write_basic(f, 'PRINT "BY RUNNING THIS COMMAND: SAVE" CHR$(34) "' + cleanname + '/BAS" CHR$(34)')
        write_basic(f, 'IF D1 = 1 THEN DELETE ' + str(data_start_line) + '-' + str(data_end_line))
        write_basic(f, 'END')

def rgb_to_bit(rgb_color):
    """
    Examine RGB color and return 1 for White and 0 for Black
    Used to build 1-bit color surface that represents TRS80 screen
    :param rgb_color: RGB Color to evaluate
    :return: 1 (black pixel) or 0 (white pixel)
    """
    if rgb_color == COLOR_WHITE:
        return 1
    else:
        return 0

def generate_trs_img_data_statements(f):
    """
    Generate TRS80 BASIC DATA statements by looping through each destination TRS pixel location
    and converting bits to an 8-bit character value (128-255)
    :param f: BASIC output file handle
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
    for y in range(1, TRS_ACTUAL_SCREEN_SIZE.h + 1, 3):      # step 3
        for x in range(1, TRS_ACTUAL_SCREEN_SIZE.w + 1, 2):  # step 2
            trs_loc = Point(x, y)

            b0 = rgb_to_bit(trs_actual_surface.get_at((trs_loc.x - 1, trs_loc.y - 1)))
            b1 = rgb_to_bit(trs_actual_surface.get_at((trs_loc.x - 1 + 1, trs_loc.y - 1)))
            b2 = rgb_to_bit(trs_actual_surface.get_at((trs_loc.x - 1, trs_loc.y - 1 + 1)))
            b3 = rgb_to_bit(trs_actual_surface.get_at((trs_loc.x - 1 + 1, trs_loc.y - 1 + 1)))
            b4 = rgb_to_bit(trs_actual_surface.get_at((trs_loc.x - 1, trs_loc.y - 1 + 2)))
            b5 = rgb_to_bit(trs_actual_surface.get_at((trs_loc.x - 1 + 1, trs_loc.y - 1 + 2)))

            byte = 128 + (b5 << 5) + (b4 << 4) + (b3 << 3) + (b2 << 2) + (b1 << 1) + b0

            data_vals += str(byte) + ','
            byte_cnt += 1

            if byte_cnt == 50:
                data_vals = data_vals[:-1]  # remove trailing comma
                write_basic(f, ' DATA ' + data_vals)
                byte_cnt = 0
                data_vals = ''

    # Output final line, if necessary
    if len(data_vals) != 0:
        data_vals = data_vals[:-1]  # remove trailing comma
        write_basic(f, ' DATA ' + data_vals)

def compute_trs_pixel_color(trs_point):
    """
    Determine if TRS pixel is white or black based on avg color of src image area
    equal in size to a TRS virtual pixel
    :param trs_point: TRS pixel location
    :return: COLOR_BLACK or COLOR_WHITE
    """

    # Locate starting/ending location of this TRS pixel in the src image display
    x_start = trs_point.x * TRS_VIRTUAL_PIXEL_SIZE.w
    x_end = x_start + TRS_VIRTUAL_PIXEL_SIZE.w

    y_start = trs_point.y * TRS_VIRTUAL_PIXEL_SIZE.h
    y_end = y_start + TRS_VIRTUAL_PIXEL_SIZE.h

    avg_val = 0
    cnt = 0

    for x in range(x_start, x_end):
        for y in range(y_start, y_end):
            color = img_display_surface.get_at((x, y))
            avg_val += (color.r + color.g + color.b) / 3.0
            cnt += 1

    if (avg_val / cnt) > CONTRAST * 2.33:
        return COLOR_WHITE
    else:
        return COLOR_BLACK

def update_display_surfaces():
    """
    Update the surface objects used to render the application displays.
    :return:
    """

    # ---------------------------------------------------------------------------------
    # Update src image display surface from orig_img_surface
    # Uses current view position as a 'window' into original image
    # Then scale this 'window' to match trs image dimensions
    # ---------------------------------------------------------------------------------

    # Work image is a 'window' into the original image.
    # This 'window' has the same proportions (width-to-height ratio) as virtual trs image
    work_img_surface.fill(COLOR_WHITE)
    work_img_surface.blit(orig_img_surface,
                          (0,0),
                          (curr_view_pos.x, curr_view_pos.y,
                           work_img_surface.get_width(),
                           work_img_surface.get_height())
                          )

    # Build the src display image (by scaling work image to display image size)
    pygame.transform.scale(work_img_surface, IMG_DISPLAY_SIZE, img_display_surface)

    # -------------------------------------------------------------------------------------
    # Update TRS actual and virtual (display) surfaces using data from img_display_surface
    # -------------------------------------------------------------------------------------

    # Re-generate TRS surfaces by looping through each actual TRS pixel
    for x in range(0, TRS_ACTUAL_SCREEN_SIZE.w):
        for y in range(0, TRS_ACTUAL_SCREEN_SIZE.h):

            # compute average pixel color by averaging all src pixels of TRS pixel size
            trs_color = compute_trs_pixel_color(Point(x, y))

            # build trs80 actual image (not displayed) (pixel is 1x1)
            trs_actual_surface.set_at((x, y), trs_color)

            # compute location of virtual TRS pixel
            virtual_trs_pos = Point(x * TRS_VIRTUAL_PIXEL_SIZE.w, y * TRS_VIRTUAL_PIXEL_SIZE.h)

            # build trs80 virtual image (displayed) by blitting virtual trs pixels
            if trs_color == COLOR_WHITE:
                trs_display_surface.blit(TRS_VIRTUAL_PIXEL_WHITE, virtual_trs_pos)
            else:
                trs_display_surface.blit(TRS_VIRTUAL_PIXEL_BLACK, virtual_trs_pos)

def draw_text():
    """
    Draw instructions on the application window (keyboard commands, etc.)
    :return:
    """

    if input_uri is not None:
        blit_text(f' Input: {input_uri}', pos=INPUT_FILE_LOC, font=FONT_SMALL, color=COLOR_WHITE)
        blit_text(f' Output: {generated_uri}', pos=OUTPUT_FILE_LOC, font=FONT_SMALL, color=COLOR_WHITE)

    blit_text('Arrows = Move Image', pos=Point(TEXT_DISPLAY_LOC.x + 50, TEXT_DISPLAY_LOC.y + 10),color=COLOR_BLACK)
    blit_text('+/- = Adjust Zoom')
    blit_text('Page Up/Page Down = Adjust Contrast')
    blit_text('Shift = Accelerate other keys')
    blit_text('R = Reset')

    if input_uri is not None:
        blit_text('G = Generate BASIC file',pos=Point(TEXT_DISPLAY_LOC.x + 440, TEXT_DISPLAY_LOC.y + 10))
    else:
        blit_text('',pos=Point(TEXT_DISPLAY_LOC.x + 440, TEXT_DISPLAY_LOC.y + 10))

    blit_text('')
    blit_text('')
    blit_text('')
    blit_text('Q = Quit program')

    blit_text(f'Zoom = {ZOOM}', pos=Point(TEXT_DISPLAY_LOC.x + 750, TEXT_DISPLAY_LOC.y + 10))
    blit_text(f'Contrast = {CONTRAST}')
    blit_text('')
    blit_text('')
    if error_msg is not None:
        blit_text(error_msg, pos=Point(100, 100), color=COLOR_WHITE)

def blit_text(txt, font=None, pos=None, antialias=True, color=None):
    """
    Common routine to draw text on the screen
    :param txt:  Text to render
    :param font: Font
    :param pos: Position to draw text at
    :param antialias: True or False
    :param color: RGB color
    :return:
    """

    global BLIT_TEXT_POS

    # NOTE: Can't use global var as default value, so add logic to replicate
    if font is None:
        font = FONT_BIG

    if pos is None:
        pos = BLIT_TEXT_POS

    if color is None:
        color = COLOR_BLACK

    rendered_text = font.render(txt, antialias, color)
    screen_surface.blit(rendered_text, pos)
    BLIT_TEXT_POS = Point(pos.x, (pos.y + rendered_text.get_height() + 4))

def zoom_factor(z):
    """
    Convert zoom to a zoom factor for calculations
    :param z: Zoom level (ie. 1-10)
    :return: Zoom factor (ie. 0.1-1.0)
    """
    return z/10.0

def is_landscape():
    """
    Determine if source image is landscape or portrait
    :return: True = landscape, False = portrait
    """
    if orig_img_surface.get_width() > orig_img_surface.get_height():
        return True
    else:
        return False

def redraw():
    """
    Redraw application screen
    :return:
    """

    global orig_view_pos
    global curr_view_pos
    global work_img_surface
    global new_image
    global move_rate
    global orig_img_surface
    global input_uri

    screen_surface.fill(COLOR_BLACK)
    pygame.draw.rect(screen_surface,
                     COLOR_GRAY,
                     (0, TEXT_DISPLAY_LOC.y, SCREEN_SIZE.w, INSTRUCTION_AREA_HEIGHT))
    draw_text()

    if input_uri is None:
        return

    # Create the work image surface
    if is_landscape():
        # landscape - base size on orig image width
        w = orig_img_surface.get_width() + (orig_img_surface.get_width() * zoom_factor(ZOOM) * -1)
        h = w / TRS_VIRTUAL_SCREEN_RATIO
        y = ((orig_img_surface.get_height() - h) / 2)
        x = 0
    else:
        # portrait - base size on orig image height
        h = orig_img_surface.get_height() + (orig_img_surface.get_height() * zoom_factor(ZOOM) * -1)
        w = h * TRS_VIRTUAL_SCREEN_RATIO
        x = ((orig_img_surface.get_width() - w) / 2)
        y = 0

    # work surface is orig image modified to match virtual trs80 ratio
    # landscape = width = orig image width.  height = compute based on width / trs ratio
    # x,y = starting location in orig display to copy to work surface
    # w,h = width to copy is orig width.  height = work surface height

    if new_image is True:
        # Move rate is 1/40th of original image width
        move_rate = int(orig_img_surface.get_width() / 40)

        orig_view_pos = Point(x, y)  # save original position for reset logic
        curr_view_pos = orig_view_pos
        new_image = False

    if w < 1:
        w = 1
    if h < 1:
        h = 1

    work_img_surface = pygame.Surface((w, h))

    update_display_surfaces()

    # Draw images to app window
    screen_surface.blit(img_display_surface, IMG_DISPLAY_LOC)
    screen_surface.blit(trs_display_surface, TRS_DISPLAY_LOC)

def update_curr_view_pos(dx, dy, shift):
    """
    Handle user source image position adjustment (ie. pan)
    :param dx: delta x position
    :param dy: delta y position
    :param shift: shift key status (True = shift is down)
    :return:
    """

    global curr_view_pos
    global move_rate

    if shift:
        dx *= MOVE_ACCELERATOR
        dy *= MOVE_ACCELERATOR

    newx = curr_view_pos.x + dx
    newy = curr_view_pos.y + dy

    orig_w = orig_img_surface.get_width()
    orig_h = orig_img_surface.get_height()
    work_w = work_img_surface.get_width()
    work_h = work_img_surface.get_height()

    if newx < (work_w * -1) + move_rate:
        newx = (work_w * -1) + move_rate
    if newx > orig_w - move_rate:
        newx = orig_w - move_rate

    if newy < (work_h * -1) + move_rate:
        newy = (work_h * -1) + move_rate
    if newy > orig_h - move_rate:
        newy = orig_h - move_rate

    curr_view_pos = Point(newx, newy)

def update_contrast(dx, shift):
    """
    Handle user contrast adjustment
    :param dx: contrast adjustment amount (+ or -)
    :param shift: shift key status (True = shift is down)
    :return:
    """

    global CONTRAST

    if shift:
        dx *= CONTRAST_ACCELERATOR

    CONTRAST += dx

    if CONTRAST < MIN_CONTRAST:
        CONTRAST = MIN_CONTRAST
        return

    if CONTRAST > MAX_CONTRAST - CONTRAST_RATE:
        CONTRAST = MAX_CONTRAST - CONTRAST_RATE
        return

def update_zoom(dx, shift):
    """
    Handle user zoom adjustment
    :param dx: zoom adjustment amount (+ or -)
    :param shift: shift key status (True = shift is down)
    :return:
    """

    global ZOOM
    global curr_view_pos

    if shift:
        dx *= ZOOM_ACCELERATOR

    prev_zoom = ZOOM

    ZOOM += dx * ZOOM_RATE

    if ZOOM < MIN_ZOOM:
        ZOOM = MIN_ZOOM

    if ZOOM > MAX_ZOOM:
        ZOOM = MAX_ZOOM

    # determine how much the zoom has changed
    # adjust current view position by this amount
    # This will prevent the display from shifting when user zooms
    delta_zoom = (zoom_factor(ZOOM) - zoom_factor(prev_zoom))

    # w = max(orig_img_surface.get_width(), work_img_surface.get_width())
    # h = max(orig_img_surface.get_height(), work_img_surface.get_height())

    if orig_img_surface.get_width() > orig_img_surface.get_height():
        # landscape - base size on orig image width
        w = orig_img_surface.get_width() + (orig_img_surface.get_width() * zoom_factor(prev_zoom))
        h = w / TRS_VIRTUAL_SCREEN_RATIO
    else:
        # portrait - base size on orig image height
        h = orig_img_surface.get_height() + (orig_img_surface.get_height() * zoom_factor(prev_zoom))
        w = h * TRS_VIRTUAL_SCREEN_RATIO

    adj_x = (w * delta_zoom) / 2.0
    adj_y = (h * delta_zoom) / 2.0
    new_x = curr_view_pos.x + adj_x
    new_y = curr_view_pos.y + adj_y

    curr_view_pos = Point(new_x, new_y)

def reset():
    """
    Reset view settings to default values
    :return:
    """
    global curr_view_pos
    global ZOOM
    global CONTRAST

    curr_view_pos = orig_view_pos
    CONTRAST = DEFAULT_CONTRAST
    ZOOM = DEFAULT_ZOOM

def init():
    """
    One time setup
    :return:
    """
    global FONT_BIG
    global FONT_SMALL

    pygame.init()
    pygame.display.set_caption("TRS Image Converter" + " v" + str(VERSION))
    pygame.key.set_repeat(50, 50)
    FONT_SMALL = pygame.font.Font(None, 22)
    FONT_BIG = pygame.font.Font(None, 24)


def handle_events():
    """
    Event loop
    :return:
    """
    global running
    global move_rate

    redraw_flag = False

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            shift = pygame.key.get_mods() & pygame.KMOD_SHIFT

            if event.key == pygame.K_q:  # QUIT
                running = False

            # No image adjustment unless image is loaded
            if input_uri is not None:
                if event.key == pygame.K_LEFT:
                    update_curr_view_pos(move_rate, 0, shift)
                    redraw_flag = True
                if event.key == pygame.K_RIGHT:
                    update_curr_view_pos(move_rate * -1, 0, shift)
                    redraw_flag = True
                if event.key == pygame.K_DOWN:
                    update_curr_view_pos(0, move_rate * -1, shift)
                    redraw_flag = True
                if event.key == pygame.K_UP:
                    update_curr_view_pos(0, move_rate, shift)
                    redraw_flag = True
                if event.key == pygame.K_PAGEDOWN:
                    update_contrast(CONTRAST_RATE, shift)
                    redraw_flag = True
                if event.key == pygame.K_PAGEUP:
                    update_contrast(CONTRAST_RATE * -1, shift)
                    redraw_flag = True

                if event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:
                    update_zoom(-1, shift)
                    redraw_flag = True
                if event.key == pygame.K_EQUALS or event.key == pygame.K_KP_PLUS:
                    update_zoom(1, shift)
                    redraw_flag = True

                if event.key == pygame.K_r:
                    reset()
                    redraw_flag = True

                if event.key == pygame.K_g:
                    generate_basic_file()
                    redraw_flag = True

            # if event.key == pygame.K_o:
            #     open_image_file()
            #     redraw_flag = True

        # Re-generate img and trs displays
        if redraw_flag:
            redraw()
            redraw_flag = False

    pygame.display.flip()
    pygame.time.wait(10)

# --------------------------------------------
# Main logic
# --------------------------------------------
check_arguments()
init()

if not open_image_file():
    pygame.quit()
    sys.exit(1)

running = True

while running:
    handle_events()

pygame.quit()
