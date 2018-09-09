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
# Requires: python 3, wxpython 4
#
# Version 1.3
# 09/09/2018
#
# By Kyle Wadsten
# kwadsten@comcast.net
#

import wx
import os.path
import json


class ApplicationFrame(wx.Frame):
    """
    Main application frame
    """
    VERSION = 1.3

    BASIC_CURR_LINE_NB = None

    BLIT_TEXT_POS = None
    BLIT_COLOR = None

    # Fonts
    FONT_SMALL = None
    FONT_BIG = None

    # Actual TRS80 screen specs
    TRS_ACTUAL_SCREEN_SIZE = wx.Size(128.0, 48.0)

    DISPLAY_SEPARATOR_WIDTH = 20        # space between src and trs displays
    INSTRUCTION_SEPARATOR_WIDTH = 50    # space between image displays and text area
    INSTRUCTION_AREA_HEIGHT = 205       # height of text area

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
    MAX_ZOOM = +50
    ZOOM_RATE = 1
    ZOOM_ACCELERATOR = 2
    ZOOM = DEFAULT_ZOOM

    # Colors
    COLOR_WHITE = wx.WHITE
    COLOR_BLACK = wx.BLACK
    COLOR_GREY = wx.LIGHT_GREY

    # Virtual TRS80 screen specs (for sample image display)
    TRS_VIRTUAL_PIXEL_SIZE = wx.Size(4, 8)
    TRS_VIRTUAL_SCREEN_SIZE = wx.Size(TRS_ACTUAL_SCREEN_SIZE.width * TRS_VIRTUAL_PIXEL_SIZE.width,
                                      TRS_ACTUAL_SCREEN_SIZE.height * TRS_VIRTUAL_PIXEL_SIZE.height)
    TRS_VIRTUAL_SCREEN_RATIO = TRS_VIRTUAL_SCREEN_SIZE.width / TRS_VIRTUAL_SCREEN_SIZE.height
    TRS_VIRTUAL_PIXEL_WHITE = None

    # Source image display size (based on virtual trs pixel size to maintain aspect ratio)
    IMG_DISPLAY_SIZE = TRS_VIRTUAL_SCREEN_SIZE

    # App screen is twice as wide as display windows + some seperator space
    SCREEN_SIZE = wx.Size((IMG_DISPLAY_SIZE.width * 2) + DISPLAY_SEPARATOR_WIDTH,
                          IMG_DISPLAY_SIZE.height + INSTRUCTION_AREA_HEIGHT)

    # Where to show images/text
    IMG_DISPLAY_LOC = wx.Point(0, 0)
    TRS_DISPLAY_LOC = wx.Point(IMG_DISPLAY_SIZE.width + DISPLAY_SEPARATOR_WIDTH, 0)
    TEXT_DISPLAY_LOC = wx.Point(0, IMG_DISPLAY_SIZE.height + INSTRUCTION_SEPARATOR_WIDTH)
    INPUT_FILE_DISPLAY_LOC = wx.Point(IMG_DISPLAY_LOC.x + 5, IMG_DISPLAY_LOC.y + IMG_DISPLAY_SIZE.height + 5)

    # Bitmaps
    src_original_img = None     # Original image
    src_original_size = None

    src_stretched_img = None    # Original image in VIRTUAL TRS aspect ratio
    src_stretched_size = None
    src_stretched_margin = None

    src_display_bmp = None      # Source image to display (viewport of src_stretched)

    trs_actual_bmp = None       # TRS image with 1x1 pixels (for output)
    trs_display_bmp = None      # TRS image for display (virtual pixel size)

    viewport_origin = None      # Position of viewport into src_stretched_bmp.  Changes with move and zoom.
    viewport_size = None        # Size of viewport.  Changes with zoom.

    input_uri = ''              # Input source image path
    output_uri = ''             # Output BASIC file path

    CONFIG_FILE = 'config.ini'
    CONFIG_FOLDERS = ['', '']   # 0=input, 1=output


    def __init__(self):
        """
        Initialize frame
        """
        super(ApplicationFrame, self).__init__(None, title='TRS Image v' + str(self.VERSION), size=self.SCREEN_SIZE,
                                               style=wx.CLOSE_BOX | wx.MINIMIZE_BOX | wx.SYSTEM_MENU)

        self.FONT_SMALL = wx.Font(wx.FontInfo(14).Family(wx.FONTFAMILY_DEFAULT).AntiAliased(True))
        self.FONT_BIG = wx.Font(wx.FontInfo(16).Family(wx.FONTFAMILY_DEFAULT).AntiAliased(True))

        self.TRS_VIRTUAL_PIXEL_WHITE = self.new_wx_bitmap(self.TRS_VIRTUAL_PIXEL_SIZE, self.COLOR_WHITE)

        # Frame events
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        # Panel is needed to capture keyboard events
        panel = wx.Panel(self)
        panel.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

        self.read_config_file()

        # Ask user for input image when application is launched
        # self.open_file()

    def OnKeyDown(self, event):
        """
        Handle keyboard events
        :param event: EVT_KEY_DOWN
        :return:
        """
        # Only need to redraw screen when user adjusts image position, size, or contrast
        redraw_flag = False

        key_code = event.GetKeyCode()
        key_char = chr(key_code)
        shift = event.ShiftDown()

        # Quit program
        if key_code == wx.WXK_ESCAPE or key_char == 'Q':
            if self.input_uri != '' and self.output_uri == '':
                answer = wx.MessageBox("Quit program without generating BASIC output file?", "Confirm",
                                       wx.YES_NO | wx.CANCEL, self)
                if answer == wx.YES:
                    self.Destroy()
            else:
                self.Destroy()

        # Open file
        if key_char == 'O':
            self.open_file()
            redraw_flag = True

        # About box
        if key_char == 'A':
            wx.MessageBox('TRS Image v' + str(self.VERSION) + '\nBy Kyle Wadsten\n2018',
                          'About', wx.OK_DEFAULT | wx.ICON_NONE, self)

        # No image adjustments allowed until image is loaded
        if self.input_uri != '':

            # Position
            if key_code == wx.WXK_LEFT:
                self.move_image(self.MOVE_RATE, 0, shift)
                redraw_flag = True
            if key_code == wx.WXK_RIGHT:
                self.move_image(self.MOVE_RATE * -1, 0, shift)
                redraw_flag = True
            if key_code == wx.WXK_UP:
                self.move_image(0, self.MOVE_RATE * -1, shift)
                redraw_flag = True
            if key_code == wx.WXK_DOWN:
                self.move_image(0, self.MOVE_RATE, shift)
                redraw_flag = True

            # Contrast
            if key_code == wx.WXK_PAGEDOWN:
                self.update_contrast(self.CONTRAST_RATE, shift)
                self.redraw(self.REDRAW_CONTRAST)
            if key_code == wx.WXK_PAGEUP:
                self.update_contrast(self.CONTRAST_RATE * -1, shift)
                self.redraw(self.REDRAW_CONTRAST)

            # Zoom
            if key_char == '_' or key_code == wx.WXK_NUMPAD_SUBTRACT:
                self.zoom_image(-1, shift)
                redraw_flag = True
            if key_char == '+' or key_code == wx.WXK_NUMPAD_ADD:
                self.zoom_image(1, shift)
                redraw_flag = True

            # Reset image size, position, and contrast
            if key_char == 'R':
                self.reset()
                redraw_flag = True

            # Generate BASIC output file
            if key_char == 'G':
                self.generate_basic_file()
                redraw_flag = True

            # Regenerate source and trs images
            if redraw_flag:
                self.redraw()

    def OnPaint(self, event):
        """
        Standard form event.  Redraws the screen.
        :param event: EVT_PAINT
        :return:
        """
        self.redraw()

    def OnClose(self, event):
        """
        Standard form event.  Closes the application.
        :param event: EVT_CLOSE
        :return:
        """
        self.Destroy()

    def generate_basic_file(self):
        """
        Output a BASIC program for TRS80 that will recreate the image.
        Uses TRS80 'String Packing' logic.
        Currently is LDOS LBASIC compatible.
        User selects output directory using a standard Folder Selection Dialog.
        Output folder is saved in a config.ini file in the program directory.
        :return:
        """
        self.BASIC_CURR_LINE_NB = 0

        with wx.DirDialog(None, message="Choose output directory",
                          style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
                          defaultPath=self.CONFIG_FOLDERS[1]) as dd:

            if dd.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

        # save the current contents in the file
        pathname = dd.GetPath()

        # save output folder to config file
        self.CONFIG_FOLDERS[1] = pathname
        self.update_config_file()

        filepath, filename = os.path.split(self.input_uri)
        basename = os.path.splitext(filename)[0]
        cleanname = ''.join(filter(str.isalnum, basename))[:8].upper()
        self.output_uri = os.path.join(pathname, cleanname + ".BAS")

        try:
            with open(self.output_uri, 'w') as f:

                self.write_basic_line(f, 'CLS')

                self.write_basic_line(f, 'PRINT"***************************************************************"')
                self.write_basic_line(f, 'PRINT"*                        TRS IMAGE                            *"')
                self.write_basic_line(f, 'PRINT"***************************************************************"')

                self.write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '..."')
                self.write_basic_line(f, 'CLEAR 1024')

                self.write_basic_line(f, 'A$="' + '.' * 128 + '"')
                self.write_basic_line(f, 'B$="' + '.' * 128 + '"')
                self.write_basic_line(f, 'C$="' + '.' * 128 + '"')
                self.write_basic_line(f, 'D$="' + '.' * 128 + '"')
                self.write_basic_line(f, 'E$="' + '.' * 128 + '"')
                self.write_basic_line(f, 'F$="' + '.' * 128 + '"')
                self.write_basic_line(f, 'G$="' + '.' * 128 + '"')
                self.write_basic_line(f, 'H$="' + '.' * 128 + '"')
                data_start_line = self.write_basic_line(f, 'D1 = 1')
                self.generate_basic_data_statements(f)

                self.write_basic_line(f, 'X=PEEK(VARPTR(A$)+2)*256+PEEK(VARPTR(A$)+1)')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
                self.write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (20%)"')
                self.write_basic_line(f, 'X=PEEK(VARPTR(B$)+2)*256+PEEK(VARPTR(B$)+1)')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
                self.write_basic_line(f, 'X=PEEK(VARPTR(C$)+2)*256+PEEK(VARPTR(C$)+1)')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
                self.write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (40%)"')
                self.write_basic_line(f, 'X=PEEK(VARPTR(D$)+2)*256+PEEK(VARPTR(D$)+1)')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
                self.write_basic_line(f, 'X=PEEK(VARPTR(E$)+2)*256+PEEK(VARPTR(E$)+1)')
                self.write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (60%)"')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
                self.write_basic_line(f, 'X=PEEK(VARPTR(F$)+2)*256+PEEK(VARPTR(F$)+1)')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
                self.write_basic_line(f, 'PRINT @467, "LOADING ' + cleanname + '... (80%)"')
                self.write_basic_line(f, 'X=PEEK(VARPTR(G$)+2)*256+PEEK(VARPTR(G$)+1)')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')
                self.write_basic_line(f, 'X=PEEK(VARPTR(H$)+2)*256+PEEK(VARPTR(H$)+1)')
                self.write_basic_line(f, 'FOR I=1 TO 128:READ J:POKE X+I-1,J:NEXT I')

                data_end_line = self.write_basic_line(f, 'CLS')
                self.write_basic_line(f, 'PRINT @0,   A$')
                self.write_basic_line(f, 'PRINT @128, B$')
                self.write_basic_line(f, 'PRINT @256, C$')
                self.write_basic_line(f, 'PRINT @384, D$')
                self.write_basic_line(f, 'PRINT @512, E$')
                self.write_basic_line(f, 'PRINT @640, F$')
                self.write_basic_line(f, 'PRINT @768, G$')
                inkey_line = self.write_basic_line(f, 'PRINT @896, LEFT$(H$, 127);')

                self.write_basic_line(f, 'K$=INKEY$:IF K$="" GOTO ' + str(inkey_line + 10))

                self.write_basic_line(f, 'CLS')
                self.write_basic_line(f, 'PRINT"**********************************************************"')
                self.write_basic_line(f, 'PRINT"* IMAGE GENERATED WITH \'TRS IMAGE\' BY KYLE WADSTEN, 2018 *"')
                self.write_basic_line(f, 'PRINT"**********************************************************"')
                self.write_basic_line(f, 'PRINT""')

                self.write_basic_line(f, 'IF D1 = 0 THEN END')
                self.write_basic_line(f, 'PRINT "THE IMAGE DATA USED BY THIS PROGRAM HAS BEEN COMPRESSED."')
                self.write_basic_line(f, 'PRINT "YOU MAY RE-SAVE THIS PROGRAM TO CONSERVE DISK SPACE"')
                self.write_basic_line(f, 'PRINT "BY RUNNING THIS COMMAND: SAVE" CHR$(34) "' + cleanname + '/BAS" CHR$(34)')
                self.write_basic_line(f, 'IF D1 = 1 THEN DELETE ' + str(data_start_line) + '-' + str(data_end_line))
                self.write_basic_line(f, 'END')

        except IOError as e:
            wx.LogError("Cannot save current data in file '%s'." % self.output_uri)

    def generate_basic_data_statements(self, file):
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
        trs_actual_as_img = self.trs_actual_bmp.ConvertToImage()

        # Note: first time through, a new data line will be created
        for y in range(1, self.TRS_ACTUAL_SCREEN_SIZE.height + 1, 3):     # step 3
            for x in range(1, self.TRS_ACTUAL_SCREEN_SIZE.width + 1, 2):  # step 2
                trs_loc = wx.Point(x, y)

                b0 = self.rgb_to_bit(trs_actual_as_img, wx.Point(trs_loc.x - 1, trs_loc.y - 1))
                b1 = self.rgb_to_bit(trs_actual_as_img, wx.Point(trs_loc.x - 1 + 1, trs_loc.y - 1))
                b2 = self.rgb_to_bit(trs_actual_as_img, wx.Point(trs_loc.x - 1, trs_loc.y - 1 + 1))
                b3 = self.rgb_to_bit(trs_actual_as_img, wx.Point(trs_loc.x - 1 + 1, trs_loc.y - 1 + 1))
                b4 = self.rgb_to_bit(trs_actual_as_img, wx.Point(trs_loc.x - 1, trs_loc.y - 1 + 2))
                b5 = self.rgb_to_bit(trs_actual_as_img, wx.Point(trs_loc.x - 1 + 1, trs_loc.y - 1 + 2))

                byte = 128 + (b5 << 5) + (b4 << 4) + (b3 << 3) + (b2 << 2) + (b1 << 1) + b0

                data_vals += str(byte) + ','
                byte_cnt += 1

                if byte_cnt == 50:
                    data_vals = data_vals[:-1]  # remove trailing comma
                    self.write_basic_line(file, ' DATA ' + data_vals)
                    byte_cnt = 0
                    data_vals = ''

        # Output final line, if necessary
        if len(data_vals) != 0:
            data_vals = data_vals[:-1]  # remove trailing comma
            self.write_basic_line(file, ' DATA ' + data_vals)

    def write_basic_line(self, f, txt):
        """
        Write a single line to the TRS80 BASIC output file.
        Increments global line number before writing line.
        Prefixes output text with current line number.
        :param f: output file handle
        :param txt: basic language text line to write
        :return: Line number just written
        """
        self.BASIC_CURR_LINE_NB += 10
        f.write(str(self.BASIC_CURR_LINE_NB) + ' ' + txt + '\r\n')

        return self.BASIC_CURR_LINE_NB

    def rgb_to_bit(self, img: wx.Image, loc: wx.Point):
        """
        Examine RGB color and return 1 for White and 0 for Black
        Used to build 1-bit color surface that represents TRS80 screen
        :param img: Source image
        :param loc: Pixel location
        :return: 1 (black pixel) or 0 (white pixel)
        """
        if img.GetRed(loc.x, loc.y)   == self.COLOR_WHITE.red and \
           img.GetGreen(loc.x, loc.y) == self.COLOR_WHITE.green and \
           img.GetBlue(loc.x, loc.y)  == self.COLOR_WHITE.blue:
            return 1
        else:
            return 0

    def draw_instructions(self, dc):
        """
        Draw instructions on the application window (keyboard commands, etc.)
        :param: dc: DC to draw text on
        :return:
        """
        if self.input_uri != '':
            self.blit_text(dc, f'    Input: {self.input_uri}', pos=self.INPUT_FILE_DISPLAY_LOC, font=self.FONT_SMALL,
                           color=self.COLOR_WHITE)
            self.blit_text(dc, f' Output: {self.output_uri}', font=self.FONT_SMALL, color=self.COLOR_WHITE)

        self.blit_text(dc, 'Arrows = Move Image', pos=wx.Point(self.TEXT_DISPLAY_LOC.x + 50, self.TEXT_DISPLAY_LOC.y + 10),
                       color=self.COLOR_BLACK)
        self.blit_text(dc, '+/- = Adjust Zoom')
        self.blit_text(dc, 'Page Up/Page Down = Adjust Contrast')
        self.blit_text(dc, 'Shift = Accelerate other keys')
        self.blit_text(dc, 'R = Reset')

        self.blit_text(dc, 'O = Open Image File', pos=wx.Point(self.TEXT_DISPLAY_LOC.x + 440, self.TEXT_DISPLAY_LOC.y + 10))
        if self.input_uri != '':
            self.blit_text(dc, 'G = Generate BASIC File')
        else:
            self.blit_text(dc, '')

        self.blit_text(dc, '')
        self.blit_text(dc, 'A = About')
        self.blit_text(dc, 'Esc or Q = Quit program')

        self.blit_text(dc, f'Zoom = {self.ZOOM}', pos=wx.Point(self.TEXT_DISPLAY_LOC.x + 750, self.TEXT_DISPLAY_LOC.y + 10))
        self.blit_text(dc, f'Contrast = {self.CONTRAST}')

    def blit_text(self, dc, txt, font=None, pos=None, color=None):
        """
        Common routine to draw text on the screen
        :param dc: DC to draw text on
        :param txt: Text to render
        :param font: Font
        :param pos: Position to draw text at
        :param color: RGB color
        :return:
        """
        # NOTE: Can't use global var as default value, so add logic to replicate
        if font is None:
            font = self.FONT_BIG

        if pos is None:
            pos = self.BLIT_TEXT_POS

        if color is None:
            color = self.COLOR_BLACK

        dc.SetTextForeground(color)

        dc.SetFont(font)
        txt_size = dc.GetTextExtent('X')
        dc.DrawText(txt, pos)
        self.BLIT_TEXT_POS = wx.Point(pos.x, (pos.y + txt_size.height + 4))

    def open_file(self):
        """
        Open an image using standard File Open Dialog.
        Input folder is saved in a config.ini file in the program directory.
        :return:
        """
        with wx.FileDialog(self, "Open image file", wildcard="JPG files (*.jpg)|*.jpg",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
                           defaultDir=self.CONFIG_FOLDERS[0]) as fd:

            if fd.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Proceed loading the file chosen by the user
            image_path = fd.GetPath()

        # Save path to config file
        filepath, filename = os.path.split(image_path)
        self.CONFIG_FOLDERS[0] = filepath
        self.update_config_file()

        # Load the image into bitmap
        try:
            self.src_original_img = wx.Image(image_path, wx.BITMAP_TYPE_ANY)
        except IOError:
            wx.MessageBox(f'Error opening {image_path}', "Open file error", wx.OK | wx.ICON_INFORMATION)
            return

        self.src_original_size = wx.Size(self.src_original_img.GetWidth(), self.src_original_img.GetHeight())

        # Resize image to match virtual trs image proportions by increasing
        # height or width.  Compute position where image will be placed.
        if (self.src_original_size.width / self.src_original_size.height) > self.TRS_VIRTUAL_SCREEN_RATIO:
            # Landscape
            w = self.src_original_size.width
            h = int(w / self.TRS_VIRTUAL_SCREEN_RATIO)
            x = 0
            y = int((h - self.src_original_size.height) / 2.0)    # should be negative
        else:
            # Portrait
            h = self.src_original_size.height
            w = int(h * self.TRS_VIRTUAL_SCREEN_RATIO)
            x = int((w - self.src_original_size.width) / 2.0)    # should be negative
            y = 0

        # Save margins to limit movement to visible area
        self.src_stretched_margin = wx.Size(x * -1, y * -1)

        # Resize image in-place by adding white border
        self.src_stretched_img = self.src_original_img.Size(wx.Size(w, h), wx.Point(x, y), red=255, blue=255, green=255)
        self.src_stretched_size = wx.Size(self.src_stretched_img.GetWidth(), self.src_stretched_img.GetHeight())

        # Set/reset default values
        self.MOVE_RATE = int(self.src_stretched_size.width / 40.0)
        self.input_uri = image_path
        self.reset()

    def redraw(self, scope=None):
        """
        Build source and trs display images and draw to application screen
        :return:
        """
        if scope is None:
            scope = self.REDRAW_ALL

        # Draw application screen (not in paint method, so use ClientDC)
        # First, fill with black, then draw grey rectangle for text area
        client_dc = wx.ClientDC(self)
        client_dc.SetBackground(wx.BLACK_BRUSH)
        client_dc.Clear()
        client_dc.SetPen(wx.GREY_PEN)
        client_dc.SetBrush(wx.GREY_BRUSH)
        client_dc.DrawRectangle(0, self.TEXT_DISPLAY_LOC.y, self.SCREEN_SIZE.width, self.INSTRUCTION_AREA_HEIGHT)

        # Draw text instructions on screen
        self.draw_instructions(client_dc)

        if self.input_uri == '':
            return

        # Update work bitmap, src display, trs display, and trs actual bitmaps using the orig image
        if scope == self.REDRAW_ALL:
            self.build_src_bitmap()

        self.build_trs_bitmaps()

        # Draw src img on screen
        client_dc.DrawBitmap(self.src_display_bmp, self.IMG_DISPLAY_LOC.x, self.IMG_DISPLAY_LOC.y)

        # Draw trs img on screen
        client_dc.DrawBitmap(self.trs_display_bmp, self.TRS_DISPLAY_LOC.x, self.TRS_DISPLAY_LOC.y)

    def build_src_bitmap(self):
        """
        Create src bitmap by copying and scaling current 'viewport' portion of original image
        :return:
        """
        self.src_display_bmp = self.new_wx_bitmap(self.IMG_DISPLAY_SIZE, self.COLOR_WHITE)
        dc_src_display = wx.MemoryDC()
        dc_src_display.SelectObject(self.src_display_bmp)

        dc_src_stretched = wx.MemoryDC()
        dc_src_stretched.SelectObject(self.src_stretched_img.ConvertToBitmap())

        #Build the src display image (by scaling original image to display image size)
        dc_src_display.StretchBlit(0, 0,
                                   self.IMG_DISPLAY_SIZE.width, self.IMG_DISPLAY_SIZE.height,
                                   dc_src_stretched,
                                   self.viewport_origin.x, self.viewport_origin.y,
                                   self.viewport_size.width, self.viewport_size.height)

        dc_src_display.SelectObject(wx.NullBitmap)
        dc_src_stretched.SelectObject(wx.NullBitmap)

    def build_trs_bitmaps(self):
        """
        Build TRS bitmaps (actual and display) using the src_display bitmap
        :return:
        """
        src_display_img = self.src_display_bmp.ConvertToImage()

        # Create new bitmaps for TRS80 image
        self.trs_display_bmp = self.new_wx_bitmap(self.TRS_VIRTUAL_SCREEN_SIZE, self.COLOR_BLACK)
        self.trs_actual_bmp = self.new_wx_bitmap(self.TRS_VIRTUAL_SCREEN_SIZE, self.COLOR_BLACK)

        dc_trs_display = wx.MemoryDC()
        dc_trs_display.SelectObject(self.trs_display_bmp)

        dc_trs_actual = wx.MemoryDC()
        dc_trs_actual.SelectObject(self.trs_actual_bmp)

        # Draw TRS surfaces by looping through each actual TRS pixel
        for x in range(0, self.TRS_ACTUAL_SCREEN_SIZE.width):
            for y in range(0, self.TRS_ACTUAL_SCREEN_SIZE.height):

                trs_pixel_loc = wx.Point(x, y)

                # compute average pixel color by averaging all src pixels of TRS pixel size
                trs_pixel_color = self.compute_trs_pixel_color(src_display_img, trs_pixel_loc)

                # build trs80 actual image (not displayed) (pixel is 1x1)
                # image default is black, so only need to draw white
                if trs_pixel_color == self.COLOR_WHITE:
                    self.new_wx_dc_draw_point(dc_trs_actual, trs_pixel_loc, self.COLOR_WHITE)

                # compute location of virtual TRS pixel
                virtual_trs_pos = wx.Point(x * self.TRS_VIRTUAL_PIXEL_SIZE.width, y * self.TRS_VIRTUAL_PIXEL_SIZE.height)

                # build trs80 virtual image (displayed) by blitting virtual trs pixels
                if trs_pixel_color == self.COLOR_WHITE:
                    dc_trs_display.DrawBitmap(self.TRS_VIRTUAL_PIXEL_WHITE, virtual_trs_pos)

        dc_trs_display.SelectObject(wx.NullBitmap)
        dc_trs_actual.SelectObject(wx.NullBitmap)

    def compute_trs_pixel_color(self, img: wx.Image, trs_pixel_loc: wx.Point):
        """
        Determine if destination TRS pixel should be black or white based on avg color of src image area
        equal in size to a TRS virtual pixel
        :param src_img: Source image
        :param trs_pixel_loc: TRS pixel location
        :return: COLOR_BLACK or COLOR_WHITE
        """

        # Locate starting/ending location of this TRS pixel in the src image display
        x_start = trs_pixel_loc.x * self.TRS_VIRTUAL_PIXEL_SIZE.width
        x_end = x_start + self.TRS_VIRTUAL_PIXEL_SIZE.width

        y_start = trs_pixel_loc.y * self.TRS_VIRTUAL_PIXEL_SIZE.height
        y_end = y_start + self.TRS_VIRTUAL_PIXEL_SIZE.height

        avg_val = 0
        cnt = 0

        for x in range(x_start, x_end):
            for y in range(y_start, y_end):
                r = img.GetRed(x, y)
                g = img.GetGreen(x, y)
                b = img.GetBlue(x, y)
                avg_val += (r + g + b) / 3.0
                cnt += 1

        if (avg_val / cnt) > 255 * (self.CONTRAST * .01):
            return self.COLOR_WHITE
        else:
            return self.COLOR_BLACK

    def move_image(self, dx, dy, shift):
        """
        Handle user source image position adjustment (viewport_origin)
        :param dx: delta x position
        :param dy: delta y position
        :param shift: shift key status (True = shift is down)
        :return:
        """
        if shift:
            dx *= self.MOVE_ACCELERATOR
            dy *= self.MOVE_ACCELERATOR

        newx = self.viewport_origin.x + dx
        newy = self.viewport_origin.y + dy

        x_max = self.src_stretched_size.width + self.src_stretched_margin.width - self.MOVE_RATE
        x_min = (-1 * self.viewport_size.width) - self.src_stretched_margin.width + self.MOVE_RATE

        y_max = self.src_stretched_size.height + self.src_stretched_margin.height - self.MOVE_RATE
        y_min = (-1 * self.viewport_size.height) - self.src_stretched_margin.height + self.MOVE_RATE

        if newx < x_min:
            newx = x_min
        if newx > x_max:
            newx = x_max

        if newy < y_min:
            newy = y_min
        if newy > y_max:
            newy = y_max

        self.viewport_origin = wx.Point(newx, newy)

    def zoom_image(self, dx, shift):
        """
        Handle user zoom adjustment
        :param dx: zoom adjustment amount (+ or -)
        :param shift: shift key status (True = shift is down)
        :return:
        """
        if shift:
            dx *= self.ZOOM_ACCELERATOR

        prev_zoom = self.ZOOM

        self.ZOOM += dx * self.ZOOM_RATE

        if self.ZOOM < self.MIN_ZOOM:
            self.ZOOM = self.MIN_ZOOM

        if self.ZOOM > self.MAX_ZOOM:
            self.ZOOM = self.MAX_ZOOM

        # determine how much the zoom has changed
        # adjust current view position by this amount
        # This will prevent the display from shifting when user zooms
        delta_zoom = (self.ZOOM / 10.0) - (prev_zoom / 10.0)

        new_viewport_width = self.viewport_size.width - (self.viewport_size.width * delta_zoom)
        new_viewport_height = self.viewport_size.height - (self.viewport_size.height * delta_zoom)

        adj_x = (self.viewport_size.width * delta_zoom) / 2.0
        adj_y = (self.viewport_size.height * delta_zoom) / 2.0
        new_x = self.viewport_origin.x + adj_x
        new_y = self.viewport_origin.y + adj_y

        self.viewport_origin = wx.Point(new_x, new_y)
        self.viewport_size = wx.Size(new_viewport_width, new_viewport_height)

    def update_contrast(self, dx, shift):
        """
        Handle user contrast adjustment
        :param dx: contrast adjustment amount (+ or -)
        :param shift: shift key status (True = shift is down)
        :return:
        """
        if shift:
            dx *= self.CONTRAST_ACCELERATOR

        self.CONTRAST += dx

        if self.CONTRAST < self.MIN_CONTRAST:
            self.CONTRAST = self.MIN_CONTRAST
            return

        if self.CONTRAST > self.MAX_CONTRAST - self.CONTRAST_RATE:
            self.CONTRAST = self.MAX_CONTRAST
            return

    def reset(self):
        """
        Reset view settings to default values
        :return:
        """
        self.viewport_origin = wx.Point(0, 0)
        self.viewport_size = self.src_stretched_size
        self.CONTRAST = self.DEFAULT_CONTRAST
        self.ZOOM = self.DEFAULT_ZOOM
        self.output_uri = ''

    def read_config_file(self):
        """
        Read or create config.ini file to store input/output folders
        :return:
        """
        try:
            if os.path.isfile(self.CONFIG_FILE):
                # Read config file to get input/output folders
                with open(self.CONFIG_FILE, 'r') as f:
                    self.CONFIG_FOLDERS = json.load(f)
        except IOError as e:
            wx.MessageBox('Error reading config file', 'Error')

    def update_config_file(self):
        """
        Update config file with input/output folders
        :return:
        """
        # Read config file to get input/output folders
        try:
            with open(self.CONFIG_FILE, 'w+') as f:
                json.dump(self.CONFIG_FOLDERS, f)
        except IOError as e:
            wx.MessageBox('Error updating config file', 'Error')

    @staticmethod
    def new_wx_bitmap(size: wx.Size, color: wx.Colour):
        """
        Helper method to create new wx.Bitmap
        :param size: Size of new bitmap
        :param color: Color of new bitmap
        :return:
        """
        return wx.Bitmap.FromRGBA(size.width, size.height,
                                  color.red, color.green, color.blue,
                                  alpha=wx.ALPHA_OPAQUE)

    @staticmethod
    def new_wx_dc_draw_point(dc: wx.MemoryDC, loc: wx.Point, color: wx.Colour):
        """
        Helper method to draw a pixel on a DC using the specified color
        :param dc:
        :param loc:
        :param color:
        :return:
        """
        dc.SetPen(wx.Pen(color))
        dc.DrawPoint(loc)

# --------------------------------------------
# Main logic
# --------------------------------------------
if __name__ == '__main__':
    # When this module is run (not imported) then create the app, the
    # frame, show it, and start the event loop.
    app = wx.App()
    frm = ApplicationFrame()
    frm.Show()
    app.MainLoop()
