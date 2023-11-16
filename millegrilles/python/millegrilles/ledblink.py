import uasyncio
import machine

LED_ONBOARD = machine.Pin('WL_GPIO0', machine.Pin.OUT)


async def __executer_sequence(led, codes: list):
    for code in codes:
        await __executer_valeur(led, code)
        await uasyncio.sleep_ms(750)
    await uasyncio.sleep_ms(2_000)
    

# Flash leds
async def __executer_valeur(led, valeur):
    for i in range(0, valeur):
        led.off()
        await uasyncio.sleep_ms(225)
        led.on()
        await uasyncio.sleep_ms(125)


async def led_executer_sequence(codes: list, executions=1, ui_lock: asyncio.Lock = None, led=LED_ONBOARD):
    led.on()
    
    await uasyncio.sleep_ms(4_000)

    if executions is not None:
        for i in range(0, executions):
            if ui_lock is not None:
                await ui_lock.acquire()
            try:
                await __executer_sequence(led, codes)
            finally:
                if ui_lock is not None:
                    ui_lock.release()
    else:
        while True:
            if ui_lock is not None:
                await ui_lock.acquire()
            try:
                await __executer_sequence(led, codes)
            finally:
                if ui_lock is not None:
                    ui_lock.release()
        
    led.off()
