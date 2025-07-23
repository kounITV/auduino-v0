from pyfirmata2 import Arduino
import time

board = Arduino('/dev/cu.usbserial-3130')

time.sleep(2)

pin = 13

try:
    while True:
        board.digital[pin].write(1)
        time.sleep(1)

        board.digital[pin].write(0)
        time.sleep(1)
finally:
    board.exit()