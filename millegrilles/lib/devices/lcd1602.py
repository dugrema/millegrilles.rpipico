import uasyncio as asyncio

from handler_devices import Driver

from .display import OutputLignes


class LCD1602(OutputLignes):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock, 16, 2)

        # Configuration LCD1602
        self._addr = 0x27
        self.__ligne = 0

    def _get_instance(self):
        from pico_i2c_lcd import FunduinoI2cLcd
        
        bus_no = self._params['bus']
        i2c = self.__busses[bus_no]
        if i2c is None:
            raise Exception('Bus %d non configure' % bus_no)

        return FunduinoI2cLcd(i2c, self._addr, self._nb_lignes, self._nb_chars)

    async def clear(self):
        self._instance.clear()

    async def preparer_ligne(self, data, flag=None):
        await self._ui_lock.acquire()
        try:
            self._instance.move_to(0, self.__ligne)
            if flag is not None:
                self._instance.putstr('{:<15}'.format(data) + flag)
            else:
                self._instance.putstr('{:<16}'.format(data).strip())
        finally:
            self.__ligne += 1
            self._ui_lock.release()

    async def show(self, attente=5.0):
        self.__ligne = 0
        await asyncio.sleep(attente)
