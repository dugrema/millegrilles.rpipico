# Module de gestions des drivers/devices
import time

import ubinascii as binascii
import uasyncio as asyncio

from json import load
from sys import print_exception

CONST_FICHIER_DEVICES = const('devices.json')

DRIVERS = dict()


class Driver:
    
    def __init__(self, appareil, params, busses, ui_lock):
        self._appareil = appareil
        self._params = params
        self._ui_lock = ui_lock
    
    @staticmethod
    def parse(appareil, params, busses, ui_lock):
        driver_name = params['driver']
        driver_class = import_driver(driver_name)
        print("Driver class: %s" % driver_class)
        return driver_class(appareil, params, busses, ui_lock)

    @property
    def device_id(self):
        return self._params['driver'].replace('.', '_')


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
        from devices.bus import Bus
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
    
    async def _lire_devices(self, sink_method, rapide=False):
        import time
        
        lectures = dict()
        ts_courant = time.time()
        for dev in self.__devices.values():
            try:
                lectures_dev = await dev.lire(rapide=rapide)
                if lectures_dev is not None:
                    for l in lectures_dev.values():
                        l['timestamp'] = ts_courant
                    lectures.update(lectures_dev)  # Transferer lectures
                if rapide is False:
                    await asyncio.sleep_ms(1)  # Liberer
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

    @property
    def devices(self):
        return self.__devices

    def get_device(self, device_id: str):
        return self.__devices[device_id]

    async def run(self, ui_lock: asyncio.Event, sink_method, feeds=None, intervalle_ms=20_000):
        if feeds is not None:
            asyncio.create_task(self._output_devices(feeds, ui_lock))

        rapide = False
        while True:
            ticks_debut = time.ticks_ms()

            # Conserver etat stale
            # permet de capturer un changement survenu apres le debut des lectures (long)
            stale = self.__appareil.stale_event.is_set()
            self.__appareil.stale_event.clear()

            await self._lire_devices(sink_method, rapide=rapide)
            print("lire_devices duree %d ms (rapide:%s)" % (time.ticks_diff(time.ticks_ms(), ticks_debut), rapide))

            if stale:
                print('DeviceHandler.run stale detecte')
                # Indiquer que l'etat a ete mis a jour et doit etre emis des que possible
                self.__appareil.emit_event.set()

            try:
                await asyncio.wait_for_ms(self.__appareil.stale_event.wait(), intervalle_ms)
                print('DeviceHandler.run stale wait jump')
                rapide = True
            except asyncio.TimeoutError:
                rapide = False


def import_driver(path_driver):
    # Separer le path en 'devices.module_py.classe'
    driver_split = path_driver.split('.')
    path_module = '.'.join(driver_split[:-1])
    last_module = driver_split[-2]
    nom_driver = driver_split[-1]

    module_devices = __import__(path_module)
    module_driver = getattr(module_devices, last_module)
    class_driver = getattr(module_driver, nom_driver)
    
    return class_driver
