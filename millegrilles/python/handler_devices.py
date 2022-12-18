# Module de gestions des drivers/devices
import ubinascii as binascii
import uasyncio as asyncio

from json import load
from sys import print_exception

from wifi import get_etat_wifi

CONST_FICHIER_DEVICES = const('devices.json')

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
    
    def __init__(self, appareil, params, busses, ui_lock):
        self._appareil = appareil
        self._params = params
        self._ui_lock = ui_lock
    
    @staticmethod
    def parse(appareil, params, busses, ui_lock):
        driver_name = params['driver'].upper()
        driver_class = DRIVERS[driver_name]
        return driver_class(appareil, params, busses, ui_lock)

    @property
    def device_id(self):
        return self._params['driver']


class RPiPicoW(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__instance = None
        self.__nb_lectures = 5

    async def load(self):
        import machine
        self.__instance = machine.ADC(4)

    async def lire(self):
        temperature = 0.0
        conversion_factor = 3.3 / (65535)
        for _ in range(0, self.__nb_lectures):
            reading = self.__instance.read_u16() * conversion_factor
            temperature += 27 - (reading - 0.706)/0.001721
            await asyncio.sleep_ms(50)

        temperature = round(temperature / self.__nb_lectures, 1)
        
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
        return 'rp2pico'


DRIVERS['RPIPICOW'] = RPiPicoW


class DriverDHT(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
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
        await asyncio.sleep_ms(1)  # Yield
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
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
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
        asyncio.sleep_ms(1)  # Yield

        self.__ds18s20_driver.convert_temp()
        # Donner le temps de faire la preparation de temperature (non-blocking)
        asyncio.sleep_ms(750)
        
        lectures = dict()
        for rom in roms:
            sname = '1W_' + binascii.hexlify(rom).decode('utf-8')
            temp = round(self.__ds18s20_driver.read_temp(rom), 1)
            lectures[sname] = {
                'valeur': temp,
                'type': 'temperature'
            }
            asyncio.sleep_ms(1)  # Yield

        return lectures


DRIVERS['ONEWIRE'] = DriverOnewire


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

    
DRIVERS['BMP180'] = DriverBmp180


class DummyOutput(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock)
        self.__instance = None
        self.__busses = busses
    
    async def load(self):
        pass
    
    async def run_display(self, feeds):
        data_generator = feeds(name=self.__class__.__name__)
        while True:
            data_lu = False
            
            lignes = data_generator.generate()
            if lignes is not None:
                for ligne, flag, duree in lignes:
                    print("Dummy output ligne : %s, flag: %s" % (ligne, flag))
                    data_lu = True
                    await asyncio.sleep(5)
            
            if data_lu is False:
                # Aucun data
                await asyncio.sleep(10)
                
    def get_display_params(self):
        return {
            'name': 'DummyOutput',
            'format': 'text',
            'width': 80,
            'height': 20,
        }


DRIVERS['DUMMYOUTPUT'] = DummyOutput


class OutputLignes(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock: asyncio.Event, nb_chars=16, nb_lignes=2, duree_afficher_datetime=10):
        super().__init__(appareil, params, busses, ui_lock)
        self._instance = None
        self.__busses = busses
        self._nb_lignes = nb_lignes
        self._nb_chars = nb_chars
        self.__duree_afficher_datetime = duree_afficher_datetime

    async def load(self):
        self._instance = self._get_instance()
        
    def _get_instance(self):
        raise Exception('Not implemented')

    async def preparer_ligne(self, data, flag=None):
        raise Exception('Not implemented')

    async def show(self, attente=5.0):
        raise Exception('Not implemented')

    async def clear(self):
        pass  # Optionnel

    async def run_display(self, feeds):
        while True:
            try:
                data_generator = feeds(name=self.__class__.__name__)
                
                # Maj duree affichage date (config)
                try:
                    self.__duree_afficher_datetime = data_generator.duree_date
                except AttributeError:
                    self.__duree_afficher_datetime = 10
                
                # Affichage heure
                await self.afficher_datetime()
                compteur = 0
                lignes = data_generator.generate(group=self._nb_lignes)
                if lignes is not None:
                    await self.clear()
                    for ligne, flag, duree in lignes:
                        compteur += 1
                        await self.preparer_ligne(ligne[:self._nb_chars], flag)
                        if compteur == self._nb_lignes:
                            compteur = 0
                            await self.show()
                            await self.clear()

                    if compteur > 0:
                        # Afficher la derniere page (incomplete)
                        for _ in range(compteur, self._nb_lignes):
                            await self.preparer_ligne('')
                        await self.show()
            
            except OSError as e:
                print("Display OSError")
                print_exception(e)
                # Attendre 30 secs avant de reessayer
                await asyncio.sleep(30)
    
    async def afficher_datetime(self):
        import time
        
        if self.__duree_afficher_datetime is None:
            return

        await self.clear()

        temps_limite = time.time() + self.__duree_afficher_datetime
        while temps_limite >= time.time():
            now = time.time()
            if self._appareil.timezone is not None:
                now += self._appareil.timezone
            (year, month, day, hour, minutes, seconds, _, _) = time.localtime(now)
            await self.preparer_ligne('{:d}-{:0>2d}-{:0>2d}'.format(year, month, day))
            await self.preparer_ligne('{:0>2d}:{:0>2d}:{:0>2d}'.format(hour, minutes, seconds))
            nouv_sec = (time.ticks_ms() % 1000) / 1000
            await self.show(nouv_sec)

    def get_display_params(self):
        return {
            'name': self.__class__.__name__,
            'format': 'text',
            'width': self._nb_chars,
            'height': self._nb_lignes,
        }


class LCD1602(OutputLignes):
    
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock, 16, 2)

        # Configuration LCD1602
        self._addr = 0x27
        self.__ligne = 0

    def _get_instance(self):
        from pico_i2c_lcd import I2cLcd
        
        bus_no = self._params['bus']
        i2c = self.__busses[bus_no]
        if i2c is None:
            raise Exception('Bus %d non configure' % bus_no)

        return I2cLcd(i2c, self._addr, self._nb_lignes, self._nb_chars)

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


DRIVERS['LCD1602'] = LCD1602


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
            raise Exception('Bus %d non configure' % bus_no)

        return SSD1306_I2C(self.__width, self.__height, i2c)

    async def preparer_ligne(self, data, flag=None):
        self._instance.text(data, 0, self.__ligne * self.__char_size)
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
        
        
DRIVERS['SSD1306'] = Ssd1306


class DeviceHandler:
    
    def __init__(self, appareil):
        self.__appareil = appareil
        self.__configuration = None
        self.__devices = dict()
        self.__busses = list()
        self.__ui_lock = None
    
    async def load(self, ui_lock: asyncio.Event):
        self.__ui_lock = ui_lock
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
                device = Driver.parse(self.__appareil, dev, self.__busses, self.__ui_lock)
                device_id = device.device_id
                print("Loading device : ", device_id)
                await device.load()
                self.__devices[device_id] = device
                print("Loaded device : ", device_id)
            except Exception as e:
                print("Erreur load device ", dev)
                print_exception(e)
    
    async def _lire_devices(self, sink_method):
        import time
        
        lectures = dict()
        ts_courant = time.time()
        for dev in self.__devices.values():
            try:
                lectures_dev = await dev.lire()
                for l in lectures_dev.values():
                    l['timestamp'] = ts_courant
                lectures.update(lectures_dev)  # Transferer lectures
                await asyncio.sleep_ms(10)  # Liberer
            except AttributeError:
                pass  # Pas d'attribut .lire
            except Exception as e:
                print("Erreur lecture")
                print_exception(e)
                
        sink_method(lectures)
        
    async def _output_devices(self, feeds, ui_lock: asyncio.Event):
        for dev in self.__devices.values():
            try:
                coro = dev.run_display(feeds)
                print("Demarrage display %s" % dev.device_id)
                asyncio.create_task(coro)
            except AttributeError:
                print("Dev %s sans output" % dev.device_id)

    def get_output_devices(self):
        outputs = list()
        for dev in self.__devices.values():
            try:
                outputs.append(dev.get_display_params())
            except AttributeError:
                pass
        
        if len(outputs) > 0:
            return outputs

    async def run(self, ui_lock: asyncio.Event, sink_method, feeds=None):
        if feeds is not None:
            asyncio.create_task(self._output_devices(feeds, ui_lock))
        
        while True:
            await self._lire_devices(sink_method)
            await asyncio.sleep(5)
