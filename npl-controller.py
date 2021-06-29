# SPDX-FileCopyrightText: 2021 Dan Begallie
# SPDX-License-Identifier: MIT

# Neopixel light controller for one Neopixel strip and one Neopixel ring.  The ring
# is used to indicate status while the strip is used for lighting.  This is controlled
# by a rotary encoder.  Pushing the encoder changes the color, rotating changes between
# one of 16 levels of brightness.
import argparse
import fcntl
import logging
import os
import sys
import time
import board
import evdev
import neopixel

##################################################################################
# IS ROOT METHOD
##################################################################################
# Method that returns True if the EUID (Effective User ID) is 0 (root) and False
# if not reboot.
##################################################################################
def is_root():
    return os.geteuid() is 0

# Make sure application is running as root.
if not is_root():
    sys.exit(-1)
# Write out file with lock to ensure only one instance of application can run
lock_file = 'npl-controller.lock'
file_open = open(lock_file, 'w')
try:
    fcntl.lockf(file_open, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    sys.exit(-1)


##################################################################################
# SHUTDOWN METHOD
##################################################################################
# Method to clean up and shutdown the application.
##################################################################################
def shutdown():
    # Turn off all lights.
    if strip:
        strip.deinit()
    if ring:
        ring.deinit()
    # Clean up devices.
    if dev_rotary:
        dev_rotary.close()
    if dev_button:
        dev_button.close()
    sys.exit(0)

##################################################################################
# RAINBOW METHOD
##################################################################################
# Method to light up pixels in a rainbow.
##################################################################################
def rainbow(pos):
    # Input a value 0 to 255 to get a color value.
    # The colors are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        r = g = b = 0
    elif pos < 85:
        r = int(pos * 3)
        g = int(255 - pos * 3)
        b = 0
    elif pos < 170:
        pos -= 85
        r = int(255 - pos * 3)
        g = 0
        b = int(pos * 3)
    else:
        pos -= 170
        r = 0
        g = int(pos * 3)
        b = int(255 - pos * 3)
    if brightness != 1:
        r = r - ((r // 5) * brightness)
        g = g - ((g // 5) * brightness)
        b = b - ((b // 5) * brightness)
    return (r, g, b) if ORDER in (neopixel.RGB, neopixel.GRB) else (r, g, b, 0)


logger = logging.getLogger("npl-controller")
logger.setLevel(logging.DEBUG)

# Create File Handler which logs all messages
file_handler = logging.FileHandler("npl-controller.log")
file_handler.setLevel(logging.DEBUG)
parser = argparse.ArgumentParser()
parser.add_argument("--log", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="WARNING")
try:
    args = parser.parse_args()
    logging_level = getattr(logging, args.log.upper(), None)
except AttributeError as e:
    logger.warning("Invalid command line attribute passed in.  Setting console logging level to WARNING")
    logging_level = getattr(logging, "WARNING", None)
# Create Console Handler with the level set to WARNING or that passed in from the
# command-line given.
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging_level)
# Create Formatter and add it to the Handlers
formatter = logging.Formatter("%(levelname)-8s %(asctime)s.%(msecs)-003d %(module)s:%(lineno)d - %(message)s",
                              "%Y/%m/%d %H:%M:%S")
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
# Add the Handlers to the Logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

WHITE = (255, 255, 255)
MAGENTA = (255, 0, 51)
PINK = (255, 51, 119)
RED = (255, 0, 0)
ORANGE = (255, 34, 0)
YELLOW = (255, 170, 0)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
AQUA = (85, 125, 255)
BLUE = (0, 0, 255)
VIOLET = (153, 0, 255)
BLACK = (0, 0, 0)
RAINBOW = (0, 0, 1)

colors = [WHITE,
          MAGENTA,
          PINK,
          RED,
          ORANGE,
          YELLOW,
          GREEN,
          CYAN,
          AQUA,
          BLUE,
          VIOLET,
          RAINBOW]

# Choose an open pin connected to the Data In of the NeoPixel strip, i.e. board.D18
# NeoPixels must be connected to D10, D12, D18 or D21 to work.
strip_pin = board.D18
ring_pin = board.D21

# The number of NeoPixels
num_pixels_strip = 30
num_pixels_ring = 16

brightness = 1
new_brightness = 1
color = BLACK
new_color = WHITE
old_color = BLACK
ORDER = neopixel.GRB
down_key = 0
value = 0

strip = neopixel.NeoPixel(strip_pin, num_pixels_strip, brightness=1.0, auto_write=False, pixel_order=ORDER)
ring = neopixel.NeoPixel(ring_pin, num_pixels_ring, brightness=1.0, auto_write=False, pixel_order=ORDER)
dev_rotary = evdev.InputDevice('/dev/input/by-path/platform-rotary@4-event')
dev_button = evdev.InputDevice('/dev/input/by-path/platform-button@1b-event')

try:
    while True:
        if new_color != color or new_brightness != brightness:
            color = new_color
            brightness = new_brightness
            if new_color == RAINBOW:
                for si in range(num_pixels_strip):
                    strip_index = (si * 256 // num_pixels_strip)
                    strip[si] = rainbow(strip_index & 255)
                for ri in range(num_pixels_ring):
                    ring_index = (ri * 256 // num_pixels_ring)
                    ring[ri] = rainbow(ring_index & 255)
            else:
                if brightness == 1:
                    strip.fill(new_color)
                    ring.fill(new_color)
                elif brightness != 0:
                    dim_new_color = (new_color[0] - ((new_color[0] // 5) * brightness),
                                        new_color[1] - ((new_color[1] // 5) * brightness),
                                        new_color[2] - ((new_color[2] // 5) * brightness))
                    strip.fill(dim_new_color)
                    ring.fill(dim_new_color)
            strip.show()
            ring.show()
        rel_event = dev_rotary.read_one()
        if rel_event:
            if brightness != 0 and rel_event.type == evdev.ecodes.EV_REL:
                value = value + rel_event.value
                if value > 11:
                    value = 0
                if value < 0:
                    value = 11
                new_color = colors[value]
            elif brightness == 0 and rel_event.type == evdev.ecodes.EV_REL:
                brightness = 1
                new_color = old_color
        key_event = dev_button.read_one()
        if key_event:
            key_event = evdev.util.categorize(key_event)
            if isinstance(key_event, evdev.events.KeyEvent):
                if key_event.keycode == "KEY_ENTER" and key_event.keystate == key_event.key_down:
                    down_key = time.time() * 1000
                if key_event.keycode == "KEY_ENTER" and key_event.keystate == key_event.key_up:
                    if down_key + 750 < time.time() * 1000:
                        brightness = 0
                        old_color = new_color
                        new_color = BLACK
                    else:
                        new_brightness = brightness + 1
                        if new_brightness > 4:
                            new_brightness = 1

except (KeyboardInterrupt, SystemExit):
    # Keeps error from displaying when CTL-C is pressed
    print(""),

shutdown()
