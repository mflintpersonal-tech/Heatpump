#!/usr/bin/env python3

#
# Do the display part
#

import sys
import time

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import ST7789

class MiniDisplay():

    def __init__(self):

        # Create ST7789 LCD display class.

        self.disp = ST7789.ST7789(
                                  height=240,
                                  width=320,
                                  rotation=0,
                                  port=0,
                                  cs=1,
                                  dc=9,
                                  backlight=13,
                                  spi_speed_hz=60 * 1000 * 1000,
                                  offset_left=0,
                                  offset_top=0
                                  )
        self.clear_screen()

    def message(self, msg, size=48, font='DejaVuSans-Bold.ttf'):

        #self.disp.reset()
        self.disp = ST7789.ST7789(
                                  height=240,
                                  width=320,
                                  rotation=0,
                                  port=0,
                                  cs=1,
                                  dc=9,
                                  backlight=13,
                                  spi_speed_hz=60 * 1000 * 1000,
                                  offset_left=0,
                                  offset_top=0
                                  )

        message = msg
        colour = (220, 164, 20)

        # creates image size of screen in black
        img = Image.new('RGB', (self.disp.width, self.disp.height), color=(0, 0, 0))

        # drawing object with image on it
        draw = ImageDraw.Draw(img)

        font = ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{font}", size)

        #size_x, size_y = draw.textsize(message, font)
        #Pillow 10 deprecates textsize
        left, top, size_x, bottom = draw.textbbox((0,0), message, font=font)
        # left top right bottom
        size_y = bottom     # (or could be bottom - top)

        text_x = self.disp.width - 80
        text_y = (self.disp.height - size_y) // 2

        # draw text onto drawing object
        x = 18
        y = 80
        draw.rectangle((0, 0, self.disp.width, self.disp.height), (0, 0, 0))
        draw.text((x, y), message, font=font, fill=colour)

        # display image
        self.disp.display(img)

    def clear_screen(self):

        # Draw a black image on the screen
        img = Image.new('RGB', (self.disp.width, self.disp.height), color=(0, 0, 0))
        self.disp.display(img)
        # and switch backlight off
        self.disp.set_backlight(0)

"""
import time
d = MiniDisplay()
d.message('Testing')
print('on!')
time.sleep(10)
print('off')
d.clear_screen()
time.sleep(4)
d.message('Testing Again')
print('on!')
time.sleep(10)
print('off')
d.clear_screen()
"""
