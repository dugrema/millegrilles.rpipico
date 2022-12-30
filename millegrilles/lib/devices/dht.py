import machine
import uasyncio as asyncio
from machine import Pin

from handler_devices import Driver

class DriverDHT(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__instance = None

    async def load(self):
        pin = self._params['pin']
        modele_str = self._params['model'].upper()

        if modele_str == 'DHT11':
            from dht import DHT11
            self.__instance = DHT11(Pin(pin))
        elif modele_str in ['DHT22', 'AM2302']:
            from dht import DHT22
            self.__instance = DHT22(Pin(pin))
        else:
            raise ValueError('DHT inconnu : %s' % modele_str)

    async def lire(self):
        self.__instance.measure()
        await asyncio.sleep_ms(1)  # Yield
        device_id = self.device_id
        return {
            '%s/temperature' % device_id: {
                'valeur': self.__instance.temperature(),
                'type': 'temperature',
            },
            '%s/humidite' % device_id: {
                'valeur': self.__instance.humidity(),
                'type': 'humidite',
            }
        }

    @property
    def device_id(self):
        pin = self._params['pin']
        modele_str = self._params['model'].upper()
        return '%s_p%d' % (modele_str, pin)
