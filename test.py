from random import randint
import time
from etherlightwin import Etherlight

#

etherlight = Etherlight("172.16.26.138","nwlab")
time.sleep(10)
# for i in range(48):
#     etherlight.set_led_color(i + 1, (0, 10, 0))
#     # time.sleep(0.1)
# etherlight.flush()
boo=True
# time.sleep(5)
# for _i in range(15):
#     for c in [(10, 0, 0), (0, 10, 0), (0, 0, 10)]:
#         for i in range(48):
#             etherlight.cache_led_color(i + 1, c)
#         etherlight.flush_led_cache()
while boo:
    for i in range(52):
        etherlight.set_led_color(i + 1, (randint(0, 255), randint(0, 255), randint(0, 255)))
    etherlight.flush()
    if i==51:
        boo=False
for i in range(52):
    etherlight.set_led_color(i + 1, (0, 0, 0))
etherlight.flush()

print("done")