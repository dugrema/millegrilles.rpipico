import _thread
import time
import uasyncio as asyncio

from millegrilles.config import get_workaround_disable_watchdog

using_core1 = False
core1_stopped = True

class Watchdog:
    def __init__(self):
        disabled = get_workaround_disable_watchdog() is True
        print("Watchdog ", end="")
        print(not disabled)
        if disabled:
            self.__wdt = None
        else:
            from machine import WDT
            self.__wdt = WDT(timeout=8388)  # Max value pour watchdog
        pass

    def feed(self):
        if not self.__wdt:
            return
        self.__wdt.feed()
        pass

    async def yield_duration(self, duration_ms):
        if not self.__wdt:
            return
        self.__wdt.feed()
        if duration_ms:
            await asyncio.sleep_ms(duration_ms)
            self.__wdt.feed()

    async def run(self):
        while True:
            if self.__wdt:
                self.__wdt.feed()
            await asyncio.sleep_ms(10)

    def start_core1(self):
        global using_core1, core1_stopped
        if not self.__wdt:
            return

        using_core1 = True
        if core1_stopped:
            _thread.start_new_thread(feed_watchdog_core1, (self.__wdt,))

    def stop_core1(self):
        global using_core1
        if not self.__wdt:
            return
        using_core1 = False

    def kill(self):
        self.__wdt = None  # Destroy reference, dog will bite

    # This class acts as a manager (with watchdog)
    def __enter__(self):
        self.start_core1()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_core1()
        if self.__wdt:
            self.__wdt.feed()
        return False

    # Note: asyncio manager does the same thing as blocking for now, future proofing
    async def __aenter__(self):
        self.start_core1()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop_core1()
        if self.__wdt:
            self.__wdt.feed()
        return False


def feed_watchdog_core1(wdt):
    global using_core1, core1_stopped
    core1_stopped = False
    print("Core 1 is dog food")
    while using_core1:
        wdt.feed()
        time.sleep(2)
    core1_stopped = True
    print("Core 1 done")


# async def watchdog_feed(wdt):
#     while True:
#         wdt.feed()
#         await asyncio.sleep_ms(10)
#
#
# async def watchdog_thread():
#     """
#     Demarre un watchdog et l'alimente
#     """
#     from machine import WDT
#     wdt = WDT(timeout=8388)  # Max value pour watchdog
#     await watchdog_feed(wdt)
