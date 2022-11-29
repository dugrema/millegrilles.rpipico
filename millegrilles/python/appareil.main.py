import ntptime
import uasyncio as asyncio
import machine
from mgthreads import connect_wifi

led_onboard = machine.Pin('WL_GPIO0', machine.Pin.OUT)


async def start():
    
    wifi_ready = await connecter_wifi()
            
    if wifi_ready is True:
        ntptime.settime()
        await blink(1.0, reps=6)
    else:
        await blink(0.2)
        

async def run():
    led_onboard.off()
    await asyncio.sleep(5)


async def connecter_wifi():
    for _ in range(0, 5):
        try:
            led_onboard.on()
            await connect_wifi()
            return True
        except:
            await blink(0.2, reps=5)
            await asyncio.sleep(3)
    
    return False


async def blink(freq=1.0, reps=None):
    led = False
    while True:
        if reps is not None:
            reps -= 1
            if reps == 0:
                break
        led = not led
        if led is True:
            led_onboard.on()
        else:
            led_onboard.off()
        await asyncio.sleep(freq)


async def main():
    await start()
    await run()


# Connecter au WIFI
asyncio.run(main())
