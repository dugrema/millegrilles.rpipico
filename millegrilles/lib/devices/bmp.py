from barometre import TendanceBarometrique
from handler_devices import Driver

from micropython import const


class DriverBmp180(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__instance = None
        self.__busses = busses
        self.__calcul = TendanceBarometrique()

    async def load(self):
        from bmp180_rpi import BMP180
        bus_no = self._params['bus']
        i2c = self.__busses[bus_no]
        if i2c is None:
            raise Exception('Bus %d non configure' % bus_no)
        self.__instance = BMP180(i2c)

    async def lire(self, rapide=False):
        if rapide is True:
            return None  # La lecture de cet appareil est lente

        (temperature, pressure, altitude) = await self.__instance.readBmp180()

        pressure_hecto = int(pressure / 100.0)

        # print("bmp180 temperature %s, pressure: %s, altitude: %s" % (temperature, pressure, altitude))

        # Conserver la lecture de pression courante pour calculer la tendance
        self.__calcul.ajouter(pressure)

        device_id = self.device_id

        valeurs = self.__calcul.get_lectures(device_id)

        # Ajouter lectures au calcul de tendance
        valeurs.update({
            '%s/temperature' % device_id: {
                'valeur': temperature,
                'type': 'temperature',
            },
            '%s/pression' % device_id: {
                'valeur': pressure_hecto,
                'type': 'pression',
            }
        })

        return valeurs

    @property
    def device_id(self):
        return 'bmp180'

    @property
    def types_lectures(self):
        return const(('temperature', 'pression'))
