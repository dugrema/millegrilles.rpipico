import machine
import uasyncio as asyncio
from machine import Pin

from handler_devices import Driver

class DriverSwitchPin(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__pin = None

    async def load(self):
        pin_no = self._params['pin']
        self.__pin = machine.Pin(pin_no, machine.Pin.OUT)

    async def lire(self):
        return {
            '%s/etat' % self.device_id: {
                'valeur': self.value,
                'type': 'switch',
            }
        }

    @property
    def value(self):
        return self.__pin.value()

    @value.setter
    def value(self, value_in: int):
        if value_in == 1:
            self.__pin.on()
        else:
            self.__pin.off()

    @property
    def device_id(self):
        pin = self._params['pin']
        return 'switch_p%d' % pin
