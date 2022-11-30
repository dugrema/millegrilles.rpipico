# Module de gestions des drivers/devices
import ubinascii as binascii
import uasyncio as asyncio
import sys
import time
from json import load


CONST_FICHIER_DEVICES = 'devices.json'

DRIVERS = dict()


class Bus:
    
    def __init__(self, params):
        self.__instance = None
    
    @staticmethod
    def parse(params):
        driver_name = params['driver'].upper()
        
        if driver_name == 'I2C':
            from machine import I2C, Pin
            bus_no = params.get('bus') or 0
            freq = params.get('freq') or 100000
            sda_pin = params['sda_pin']
            scl_pin = params['scl_pin']
            return I2C(bus_no, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=freq)
        else:
            raise Exception('bus %s not implemented' % driver_name)


class Driver:
    
    def __init__(self, params, busses):
        self._params = params
    
    @staticmethod
    def parse(params, busses):
        driver_name = params['driver'].upper()
        driver_class = DRIVERS[driver_name]
        return driver_class(params, busses)

    @property
    def device_id(self):
        return self._params['driver']


class DriverDHT(Driver):
    
    def __init__(self, params, busses):
        super().__init__(params, busses)
        self.__instance = None

    async def load(self):
        pin = self._params['pin']
        modele_str = self._params['model'].upper()

        if modele_str == 'DHT11':
            from machine import Pin
            from dht import DHT11
            self.__instance = DHT11(Pin(pin))
        elif modele_str in ['DHT22', 'AM2302']:
            from machine import Pin
            from dht import DHT22
            self.__instance = DHT22(Pin(pin))
        else:
            raise ValueError('DHT inconnu : %s' % modele_str)

    async def lire(self):
        self.__instance.measure()
        await asyncio.sleep(0.001)  # Yield
        device_id = self.device_id
        return {
            '%s/temperature' % device_id: {
                'valeur': self.__instance.temperature(),
                'type': 'temperature',
            },
            '%s/humidite' % device_id: {
                'valeur': self.__instance.humidity(),
                'type': 'humidite',
            }
        }

    @property
    def device_id(self):
        pin = self._params['pin']
        modele_str = self._params['model'].upper()
        return '%s_p%d' % (modele_str, pin)


DRIVERS['DHT'] = DriverDHT


class DriverOnewire(Driver):
    
    def __init__(self, params, busses):
        super().__init__(params, busses)
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
                'valeur': temp,
                'type': 'temperature'
            }
            asyncio.sleep(0.001)  # Yield

        return lectures


DRIVERS['ONEWIRE'] = DriverOnewire


class DriverBmp180(Driver):
    
    def __init__(self, params, busses):
        super().__init__(params, busses)
        self.__instance = None
        self.__busses = busses

    async def load(self):
        from bmp180_rpi import BMP180
        bus_no = self._params['bus']
        i2c = self.__busses[bus_no]
        print("Bus i2c ", i2c)
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

    
DRIVERS['BMP180'] = DriverBmp180


class DeviceHandler:
    
    def __init__(self):
        self.__configuration = None
        self.__devices = dict()
        self.__busses = list()
    
    async def load(self):
        with open(CONST_FICHIER_DEVICES, 'rb') as fichier:
            self.__configuration = load(fichier)
        print("Configuration devices %s" % self.__configuration)

        try:
            await self._configurer_busses()
        except KeyError:
            print("Aucuns bus configures")
            
        await self._configurer_devices()
        
    async def _configurer_busses(self):
        busses = self.__configuration['bus']
        print("_configurer devices ", self.__configuration)
        for bus_params in busses:
            bus_name = bus_params.get('driver')
            print("Ajout bus %s[%d]" % (bus_name, len(self.__busses)))
            bus_instance = Bus.parse(bus_params)
            self.__busses.append(bus_instance)

    async def _configurer_devices(self):
        devices_list = self.__configuration['devices']
        print("Devices list : %s" % devices_list)
        for dev in devices_list:
            print("Device : %s" % dev)
            try:
                device = Driver.parse(dev, self.__busses)
                device_id = device.device_id
                print("Loading device : ", device_id)
                await device.load()
                self.__devices[device_id] = device
                print("Loaded device : ", device_id)
            except Exception as e:
                print("Erreur load device ", dev)
                sys.print_exception(e)
    
    async def _lire_devices(self, sink_method):
        lectures = dict()
        ts_courant = time.time()
        for dev in self.__devices.values():
            lectures_dev = await dev.lire()
            for l in lectures_dev.values():
                l['timestamp'] = ts_courant
            lectures.update(lectures_dev)  # Transferer lectures
            await asyncio.sleep(0.01)  # Liberer
        
        sink_method(lectures)

    async def run(self, sink_method):
        while True:
            await self._lire_devices(sink_method)
            await asyncio.sleep(5)
