from appareil_millegrille import main
from uasyncio import run
from time import sleep_ms
from machine import Pin

LED_ONBOARD = Pin('WL_GPIO0', machine.Pin.OUT)
for _ in range(0, 6):
    LED_ONBOARD.on()
    sleep_ms(250)
    LED_ONBOARD.off()
    sleep_ms(250)

run(main())
