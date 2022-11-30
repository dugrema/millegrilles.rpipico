# Module de gestions des drivers/devices
import uasyncio as asyncio
import sys
from json import load


CONST_FICHIER_DEVICES = 'devices.json'

DRIVERS = dict()


class Driver:
    
    def __init__(self, params):
        self._params = params
    
    @staticmethod
    def parse(params):
        driver_name = params['driver']
        driver_class = DRIVERS[driver_name]
        return driver_class(params)

    @property
    def device_id(self):
        return self._params['driver']


class DriverDHT(Driver):
    
    def __init__(self, params):
        super().__init__(params)
        self.__instance = None

    async def load(self):
        import machine

        pin = self._params['pin']
        modele_str = self._params['model'].upper()

        if modele_str == 'DHT11':
            import machine
            from dht import DHT11
            self.__instance = DHT11(machine.Pin(pin))
        elif modele_str in ['DHT22', 'AM2302']:
            import machine
            from dht import DHT11
            self.__instance = DHT11(machine.Pin(pin))
        else:
            raise ValueError('DHT inconnu : %s' % modele_str)

        return self.__instance

    async def lire(self):
        self.__instance.measure()
        await asyncio.sleep(0.001)  # Yield
        return {
            'temperature': self.__instance.temperature(),
            'humidite': self.__instance.humidity(),
        }


DRIVERS['DHT'] = DriverDHT


class DeviceHandler:
    
    def __init__(self):
        self.__configuration = None
        self.__devices = dict()
    
    async def load(self):
        with open(CONST_FICHIER_DEVICES, 'rb') as fichier:
            self.__configuration = load(fichier)
        print("Configuration devices %s" % self.__configuration)

        await self._configurer_devices()

    async def _configurer_devices(self):
        print("_configurer devices ", self.__configuration)
        devices_list = self.__configuration['devices']
        print("Devices list : %s" % devices_list)
        for dev in devices_list:
            print("Device : %s" % dev)
            try:
                device = Driver.parse(dev)
                device_id = device.device_id
                print("Loading device : ", device_id)
                await device.load()
                self.__devices[device_id] = device
                print("Loaded device : ", device_id)
            except Exception as e:
                print("Erreur load device ", dev)
                sys.print_exception(e)
    
    async def _lire_devices(self):
        lectures = dict()
        for dev in self.__devices.values():
            lectures[dev.device_id] = await dev.lire()
            await asyncio.sleep(0.01)  # Liberer
        
        print("Lectures\n%s" % lectures)

    async def run(self):
        while True:
            await self._lire_devices()
            await asyncio.sleep(5)
    