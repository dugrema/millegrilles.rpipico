import uasyncio as asyncio

from devices.display import OutputLignes

CONST_ERROR_BUS_NON_CONFIGURE = const('Bus %d non configure')


class Ssd1306(OutputLignes):
    
    def __init__(self, appareil, params, busses, ui_lock, width=128, height=32, char_size=8):
        nb_chars = params.get('chars') or 16
        nb_lines = params.get('lines') or 4
        super().__init__(appareil, params, busses, ui_lock, nb_chars, nb_lines)
        self.__ligne = 0
        self.__width = params.get('width') or width
        self.__height = params.get('height') or height
        self.__char_size = char_size

    def _get_instance(self):
        from ssd1306 import SSD1306_I2C
        
        bus_no = self._params['bus']
        i2c = self.__busses[bus_no]
        if i2c is None:
            raise Exception(CONST_ERROR_BUS_NON_CONFIGURE % bus_no)

        return SSD1306_I2C(self.__width, self.__height, i2c)

    async def preparer_ligne(self, data, flag=None):
        ligne_data = ('{:<%d}' % self._nb_chars).format(data).strip()
        if flag is not None:
            ligne_data = ligne_data[:self._nb_chars-1] + flag
        self._instance.text(ligne_data, 0, self.__ligne * self.__char_size)
        self.__ligne += 1

    async def show(self, attente=5.0):
        self.__ligne = 0
        await self._ui_lock.acquire()
        try:
            self._instance.show()
        finally:
            self._ui_lock.release()
        await asyncio.sleep(attente)
        self._instance.fill(0)
        
        