import uasyncio as asyncio

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
        await asyncio.sleep_ms(1)

    async def preparer_ligne(self, data, flag=None):
        await self._ui_lock.acquire()
        try:
            self._instance.move_to(0, self.__ligne)
            await asyncio.sleep_ms(5)
            ligne_data = '{:<16}'.format(data)
            if flag is not None:
                ligne_data = ligne_data[:15] + flag
            self._instance.putstr(ligne_data)
            await asyncio.sleep_ms(5)
        finally:
            self.__ligne += 1
            self._ui_lock.release()

    async def show(self, attente=5.0):
        self.__ligne = 0
        await asyncio.sleep(attente)

    def set_ligne(self, ligne):
        self.__ligne = ligne
