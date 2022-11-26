import uasyncio
import machine

LED_ONBOARD = machine.Pin('WL_GPIO0', machine.Pin.OUT)

# Flash leds
async def __executer_valeur(led, valeur):
    for i in range(0, valeur):
        led.off()
        await uasyncio.sleep_ms(225)
        led.on()
        await uasyncio.sleep_ms(125)
        
async def led_executer_sequence(codes: list, executions=1, led=LED_ONBOARD):
    led.on()
    
    await uasyncio.sleep_ms(4_000)
    for i in range(0, executions):
        for code in codes:
            await __executer_valeur(led, code)
            await uasyncio.sleep_ms(750)
        await uasyncio.sleep_ms(2_000)

    led.off()
