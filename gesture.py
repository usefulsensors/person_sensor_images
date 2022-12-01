import adafruit_imageload
import board
import busio
import displayio
import struct
import time


# The gesture sensor has the I2C ID of hex 62, or decimal 98.
GESTURE_SENSOR_I2C_ADDRESS = 0x62

# We will be reading raw bytes over I2C, and we'll need to decode them into
# data structures. These strings define the format used for the decoding, and
# are derived from the layouts defined in the developer guide.
GESTURE_SENSOR_I2C_HEADER_FORMAT = 'BBH'
GESTURE_SENSOR_I2C_HEADER_BYTE_COUNT = struct.calcsize(
    GESTURE_SENSOR_I2C_HEADER_FORMAT)

GESTURE_SENSOR_MSG_FORMAT = 'BBBBBBb'
GESTURE_SENSOR_MSG_BYTE_COUNT = struct.calcsize(GESTURE_SENSOR_MSG_FORMAT)

GESTURE_SENSOR_MSG_MAX = 4
GESTURE_SENSOR_RESULT_FORMAT = GESTURE_SENSOR_I2C_HEADER_FORMAT + \
    'B' + GESTURE_SENSOR_MSG_FORMAT * GESTURE_SENSOR_MSG_MAX + 'H'
GESTURE_SENSOR_RESULT_BYTE_COUNT = struct.calcsize(GESTURE_SENSOR_RESULT_FORMAT)

# How long to pause between sensor polls.
GESTURE_SENSOR_DELAY = 0.05


GESTURES = {
    0: 'no_gesture',
    1: 'call',
    2: 'dislike',
    3: 'fist',
    4: 'four',
    5: 'like',
    6: 'mute',
    7: 'ok',
    8: 'one',
    9: 'palm',
    10: 'peace',
    11: 'rock',
    12: 'stop',
    13: 'stop_inverted',
    14: 'three',
    15: 'two_up',
    16: 'two_up_inverted',
    17: 'three2',
    18: 'peace_inverted',
}


class Emoji(object):
    def __init__(self, group, filename):
        sheet, palette = adafruit_imageload.load(
            filename,
            bitmap=displayio.Bitmap,
            palette=displayio.Palette)
        palette.make_transparent(0)
        emoji = displayio.TileGrid(
            sheet,
            pixel_shader=palette,
            width=1,
            height=1,
            tile_width=64,
            tile_height=64,
            default_tile=0,
        )
        temp_group = displayio.Group()
        temp_group.append(emoji)
        group.append(temp_group)
        emoji = temp_group
        emoji.hidden = True
        emoji.scale = 2
        emoji.x = 80
        emoji.y = 30
        self.emoji = emoji

    def hide(self):
        self.emoji.hidden = True

    def show(self):
        self.emoji.hidden = False


def get_i2c():
    # The Pico doesn't support board.I2C(), so check before calling it. If it isn't
    # present then we assume we're on a Pico and call an explicit function.
    try:
        i2c = board.I2C()
    except:
        i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

    # Wait until we can access the bus.
    while not i2c.try_lock():
        pass
    return i2c


def get_gesture_packets():
    i2c = get_i2c()
    last_seen = bytearray(GESTURE_SENSOR_RESULT_BYTE_COUNT)
    i2c.readfrom_into(GESTURE_SENSOR_I2C_ADDRESS, last_seen)
    last_seen_count = 0
    while True:        
        read_data = bytearray(GESTURE_SENSOR_RESULT_BYTE_COUNT)
        i2c.readfrom_into(GESTURE_SENSOR_I2C_ADDRESS, read_data)

        if last_seen == read_data and last_seen_count < 3:
            print('last seen same, continuing')
            last_seen_count += 1
            time.sleep(GESTURE_SENSOR_DELAY)
            continue
        last_seen_count = 0
        last_seen = read_data

        offset = 0
        (pad1, pad2, payload_bytes) = struct.unpack_from(
            GESTURE_SENSOR_I2C_HEADER_FORMAT, read_data, offset)
        offset = offset + GESTURE_SENSOR_I2C_HEADER_BYTE_COUNT

        (num_hands) = struct.unpack_from('B', read_data, offset)
        num_hands = int(num_hands[0])
        if num_hands == 0:
            print('No hands, continuing')
            continue
        offset = offset + 1

        hands = []
        for _ in range(num_hands):
            (box_confidence, box_left, box_top, box_right, box_bottom, id_confidence, id_) = struct.unpack_from(GESTURE_SENSOR_MSG_FORMAT, read_data, offset)
            offset = offset + GESTURE_SENSOR_MSG_BYTE_COUNT
            hand = {
                'box_confidence': box_confidence,
                'box_left': box_left,
                'box_top': box_top,
                'box_right': box_right,
                'box_bottom': box_bottom,
                'id_confidence': id_confidence,
                'id': id_
            }
            hands.append(hand)
        checksum = struct.unpack_from('H', read_data, offset)
        yield(hands)

def main():
    try:
        display = board.DISPLAY
    except:
        display = None
    if display:
        group = displayio.Group()

        bitmap = displayio.Bitmap(display.width, display.height, 2)
        palette = displayio.Palette(2)
        palette[0] = 0x000000
        palette[1] = 0xffff00
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        group.append(tile_grid)
        
        emojis = dict()
        emojis['like'] = Emoji(group, 'images/thumbs_up.bmp')
        emojis['dislike'] = Emoji(group, 'images/thumbs_down.bmp')
        emojis['palm'] = Emoji(group, 'images/palm.bmp')
        emojis['stop_inverted'] = Emoji(group, 'images/palm.bmp')
        emojis['fist'] = Emoji(group, 'images/fist.bmp')
        emojis['peace'] = Emoji(group, 'images/peace.bmp')
        emojis['rock'] = Emoji(group, 'images/rock.bmp')
        emojis['ok'] = Emoji(group, 'images/ok.bmp')
        emojis['mute'] = Emoji(group, 'images/mute.bmp')


        emojis['no_gesture'] = Emoji(group, 'images/eyes.bmp')
        emojis['eyes'] = Emoji(group, 'images/eyes.bmp')
        display.show(group)

        showing = emojis['eyes']
        showing.show()

    tries = 0
    for hands in get_gesture_packets():
        print(hands)
        gesture = hands[0] if hands else None
        if (gesture is None or
            # gesture['box_confidence'] < 70 or
            gesture['id_confidence'] < 90 or
            gesture['id'] not in GESTURES):
            tries += 1
            if tries == 10:
                tries = 0
                if display:
                    showing.hide()
                    showing = emojis['eyes']
                    showing.show()
            continue
        gesture_name = GESTURES[gesture['id']]
        print(gesture_name, gesture['id_confidence'], gesture['box_confidence'])
        if display and gesture_name in emojis:
            showing.hide()
            showing = emojis[gesture_name]
            showing.show()


if __name__ == '__main__':
    main()
