import machine
import uasyncio as asyncio
from handler_devices import Driver

from millegrilles.wifi import get_etat_wifi

class RPiPicoW(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__instance = None
        self.__nb_lectures = 5

    async def load(self):
        self.__instance = machine.ADC(4)

    async def lire(self):
        temperature = 0.0
        conversion_factor = 3.3 / (65535)
        for _ in range(0, self.__nb_lectures):
            reading = self.__instance.read_u16() * conversion_factor
            temperature += 27 - (reading - 0.706)/0.001721
            await asyncio.sleep_ms(50)

        temperature = round(temperature / self.__nb_lectures, 1)
        
        device_id = self.device_id
        return {
            '%s/temperature' % device_id: {
                'valeur': temperature,
                'type': 'temperature',
            },
            '%s/wifi' % device_id: {
                'valeur_str': get_etat_wifi()['ip'],
                'type': 'ip',
            }            
        }

    @property
    def device_id(self):
        return 'rp2picow'
