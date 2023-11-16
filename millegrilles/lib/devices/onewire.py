import onewire
import uasyncio as asyncio
import ubinascii as binascii
from machine import Pin

from handler_devices import Driver

class DriverOnewire(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__bus = None
        self.__ds18s20_driver = None

    async def load(self):

        # Charger bus 1W
        pin_id = self._params['pin']
        ds_pin = Pin(pin_id)
        self.__bus = onewire.OneWire(ds_pin)

        # Activer drivers modeles
        modeles_str = [m.upper() for m in self._params['models']]
        if 'DS18X20' in modeles_str:
            import ds18x20
            self.__ds18s20_driver = ds18x20.DS18X20(self.__bus)
            print("1W ds18x20 active")

    async def lire(self, rapide=False):
        if rapide is True:
            return None  # La lecture de cet appareil est lente

        if self.__ds18s20_driver is not None:
            return await self.lire_temperatures()
        
        return dict()

    async def lire_temperatures(self):
        roms = self.__bus.scan()
        await asyncio.sleep_ms(1)  # Yield

        self.__ds18s20_driver.convert_temp()
        # Donner le temps de faire la preparation de temperature (non-blocking)
        await asyncio.sleep_ms(750)
        
        lectures = dict()
        for rom in roms:
            sname = '1W_' + binascii.hexlify(rom).decode('utf-8')
            temp = round(self.__ds18s20_driver.read_temp(rom), 1)
            lectures[sname] = {
                'valeur': temp,
                'type': 'temperature'
            }
            await asyncio.sleep_ms(1)  # Yield

        return lectures
