import uasyncio as asyncio

from handler_devices import Driver


class DriverBmp180(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__instance = None
        self.__busses = busses

    async def load(self):
        from bmp180_rpi import BMP180
        bus_no = self._params['bus']
        i2c = self.__busses[bus_no]
        if i2c is None:
            raise Exception('Bus %d non configure' % bus_no)
        self.__instance = BMP180(i2c)

    async def lire(self):
        (temperature,pressure,altitude) = await self.__instance.readBmp180()
        device_id = self.device_id
        return {
            '%s/temperature' % device_id: {
                'valeur': temperature,
                'type': 'temperature',
            },
            '%s/pression' % device_id: {
                'valeur': pressure,
                'type': 'pression',
            }
        }

