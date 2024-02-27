import machine
import uasyncio as asyncio
from handler_devices import Driver
from micropython import const

from millegrilles.wifi import get_etat_wifi


class RPiPicoW(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__instance = None
        self.__nb_lectures = 5

    async def load(self):
        self.__instance = machine.ADC(4)

    async def lire(self, rapide=False):
        temperature = 0.0
        if rapide is True:
            nb_lectures = 1
        else:
            nb_lectures = self.__nb_lectures

        for i in range(0, nb_lectures):
            temperature += convert(self.__instance.read_u16())
            await asyncio.sleep_ms(1)

        temperature = round(temperature / nb_lectures, 1)
        
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

    @property
    def types_lectures(self):
        return const(('temperature', 'ip'))


def convert(reading):
    voltage = reading * const(3.3 / 65535)
    return 27 - (voltage - 0.706) / 0.001721
