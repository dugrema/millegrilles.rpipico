# Module de gestions des drivers/devices
import ubinascii as binascii
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
        driver_name = params['driver'].upper()
        driver_class = DRIVERS[driver_name]
        return driver_class(params)

    @property
    def device_id(self):
        return self._params['driver']


class Bus:
    
    def __init__(self, params):
        self.__instance = None
    
    @staticmethod
    def parse(params):
        driver_name = params['driver'].upper()
        
        if driver_name == 'I2C':
            pass
        raise Exception('not implemented')


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

    async def lire(self):
        self.__instance.measure()
        await asyncio.sleep(0.001)  # Yield
        return {
            self.device_id: {
                'temperature': self.__instance.temperature(),
                'humidite': self.__instance.humidity(),
            }
        }

    @property
    def device_id(self):
        pin = self._params['pin']
        modele_str = self._params['model'].upper()
        return '%s_p%d' % (modele_str, pin)


DRIVERS['DHT'] = DriverDHT


class DriverOnewire(Driver):
    
    def __init__(self, params):
        super().__init__(params)
        self.__bus = None
        self.__ds18s20_driver = None

    async def load(self):
        import machine
        import onewire

        # Charger bus 1W
        pin_id = self._params['pin']
        ds_pin = machine.Pin(pin_id)
        self.__bus = onewire.OneWire(ds_pin)

        # Activer drivers modeles
        modeles_str = [m.upper() for m in self._params['models']]
        if 'DS18X20' in modeles_str:
            import ds18x20
            self.__ds18s20_driver = ds18x20.DS18X20(self.__bus)
            print("1W ds18x20 active")

    async def lire(self):
        if self.__ds18s20_driver is not None:
            return await self.lire_temperatures()
        
        return dict()

    async def lire_temperatures(self):
        roms = self.__bus.scan()
        asyncio.sleep(0.001)  # Yield

        self.__ds18s20_driver.convert_temp()
        # Donner le temps de faire la preparation de temperature (non-blocking)
        asyncio.sleep(0.750)
        
        lectures = dict()
        for rom in roms:
            sname = '1W_' + binascii.hexlify(rom).decode('utf-8')
            temp = round(self.__ds18s20_driver.read_temp(rom), 1)
            lectures[sname] = {
                'temperature': temp,
            }
            asyncio.sleep(0.001)  # Yield

        return lectures


DRIVERS['ONEWIRE'] = DriverOnewire


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
    