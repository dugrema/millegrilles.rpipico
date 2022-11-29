import appareil_millegrille
import uasyncio as asyncio
import time

LED_ONBOARD = machine.Pin('WL_GPIO0', machine.Pin.OUT)
LED_ONBOARD.on()
time.sleep(3)
LED_ONBOARD.off()

asyncio.run(appareil_millegrille.main())
