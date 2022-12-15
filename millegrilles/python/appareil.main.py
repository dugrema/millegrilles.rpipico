from uasyncio import run
from time import sleep_ms
from machine import Pin, reset
from sys import print_exception

LED_ONBOARD = Pin('WL_GPIO0', machine.Pin.OUT)

# Initialiser bus
print("main()")
sleep_ms(100)


def flash_led(cycles=6):
    for _ in range(0, cycles):
        LED_ONBOARD.on()
        sleep_ms(250)
        LED_ONBOARD.off()
        sleep_ms(250)


try:
    from appareil_millegrille import main
    flash_led()
    run(main())
except Exception as e:
    print("Erreur main")
    print_exception(e)
    e = None
    flash_led(120)
    reset()

