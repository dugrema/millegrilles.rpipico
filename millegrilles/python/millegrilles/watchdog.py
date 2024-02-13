import uasyncio as asyncio


async def watchdog_feed(wdt):
    while True:
        wdt.feed()
        await asyncio.sleep_ms(500)


async def watchdog_thread():
    """
    Demarre un watchdog et l'alimente
    """
    from machine import WDT
    wdt = WDT(timeout=8388)  # Max value pour watchdog
    await watchdog_feed(wdt)
