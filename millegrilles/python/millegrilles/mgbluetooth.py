import uasyncio as asyncio
import bluetooth
import aioble
import json
import struct
import sys
import time

from micropython import const
from gc import collect
from millegrilles.message_inscription import NOM_APPAREIL
from millegrilles.wifi import pack_info_wifi
from millegrilles import constantes
from millegrilles.config import get_nom_appareil


# # org.bluetooth.service.environmental_sensing
# _ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# # org.bluetooth.characteristic.temperature
# _ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A6E)
# # org.bluetooth.characteristic.humidity
# _ENV_SENSE_HUM_UUID = bluetooth.UUID(0x2A6F)
# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)

# Service de configuration MilleGrilles
_ENV_COMMAND_UUID = bluetooth.UUID('7aac7580-88d7-480f-8a01-65406c2decaf')
_ENV_COMMAND_WRITE_UUID = bluetooth.UUID('7aac7581-88d7-480f-8a01-65406c2decaf')

# Service d'etat appareil MilleGrille
_ENV_ETAT_UUID = bluetooth.UUID('7aac7590-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_USERID_UUID = bluetooth.UUID('7aac7591-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_IDMG_UUID = bluetooth.UUID('7aac7592-88d7-480f-8a01-65406c2decaf')
# _ENV_ETAT_WIFI1_UUID = bluetooth.UUID('7aac7593-88d7-480f-8a01-65406c2decaf')
# _ENV_ETAT_WIFI2_UUID = bluetooth.UUID('7aac7594-88d7-480f-8a01-65406c2decaf')
# _ENV_ETAT_TIME_UUID = bluetooth.UUID('7aac7595-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_WIFI_UUID = bluetooth.UUID('7aac7596-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_LECTURES_UUID = bluetooth.UUID('7aac7597-88d7-480f-8a01-65406c2decaf')

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = const(250_000)


class BluetoothHandler:
    """ Classe principale pour Bluetooth. Utiliser run(). """

    def __init__(self, runner, optionnel=False):
        self.__runner = runner  # Appareil
        self.__optionnel = optionnel

        self.__temp_service = None
        self.__command_service = None
        self.__etat_service = None

        self.__temp_characteristic = None
        self.__hum_characteristic = None

        self.__command_write_characteristic = None

        self.__getetat_idmg_characteristic = None
        self.__getetat_userid_characteristic = None
        # self.__getetat_wifi1_characteristic = None
        # self.__getetat_wifi2_characteristic = None
        # self.__getetat_time_characteristic = None
        self.__getetat_wifi_characteristic = None
        self.__getetat_lectures_characteristic = None

        self.__devices_lecture_map = None
        self.__lectures_sticky = dict()

    async def __initialiser(self):
        collect()
        self.preparer_gatt_server()
        collect()
        await asyncio.sleep(0)  # Yield

        self.load_profil_config()
        await asyncio.sleep(0)  # Yield
        collect()
        await asyncio.sleep(0)  # Yield

        await self.initialiser_devices_lectures()

    async def initialiser_devices_lectures(self):
        devices = self.__runner.get_devices()
        devices_dict = dict()
        for d in devices:
            ble_value = d.ble
            if isinstance(ble_value, str):
                devices_dict[ble_value] = d
            elif d.ble is True:
                devices_dict[d.device_id] = d

        # Trier keys
        device_ids = sorted(devices_dict.keys())
        devices_map = dict()
        # Remplir types lecture en ordre (specifiquement temperatures et switch)
        for did in device_ids:
            device = devices_dict[did]
            types_lectures = device.types_lectures
            if types_lectures is None:
                continue

            for tl in types_lectures:
                try:
                    dm = devices_map[tl]
                except KeyError:
                    dm = list()
                    devices_map[tl] = dm
                dm.append(did)

        print("BLE init Device ", devices_map)
        self.__devices_lecture_map = devices_map

    def preparer_gatt_server(self):
        # Register GATT server.

        # Config
        self.__command_service = aioble.Service(_ENV_COMMAND_UUID)
        self.__command_write_characteristic = aioble.Characteristic(
            self.__command_service, _ENV_COMMAND_WRITE_UUID, write=True, capture=True, notify=True
        )

        # Etat
        self.__etat_service = aioble.Service(_ENV_ETAT_UUID)
        self.__getetat_idmg_characteristic = aioble.BufferedCharacteristic(
            self.__etat_service, _ENV_ETAT_IDMG_UUID, read=True, max_len=56
        )
        self.__getetat_userid_characteristic = aioble.BufferedCharacteristic(
            self.__etat_service, _ENV_ETAT_USERID_UUID, read=True, max_len=51
        )
        # self.__getetat_wifi1_characteristic = aioble.Characteristic(
        #     self.__etat_service, _ENV_ETAT_WIFI1_UUID, read=True, notify=True
        # )
        # self.__getetat_wifi2_characteristic = aioble.Characteristic(
        #     self.__etat_service, _ENV_ETAT_WIFI2_UUID, read=True, notify=True
        # )
        # self.__getetat_time_characteristic = aioble.Characteristic(
        #     self.__etat_service, _ENV_ETAT_TIME_UUID, read=True, notify=True
        # )
        self.__getetat_wifi_characteristic = aioble.BufferedCharacteristic(
            self.__etat_service, _ENV_ETAT_WIFI_UUID, read=True, notify=True, max_len=39
        )
        self.__getetat_lectures_characteristic = aioble.Characteristic(
            self.__etat_service, _ENV_ETAT_LECTURES_UUID, read=True, notify=True
        )

        # aioble.register_services(self.__etat_service, self.__command_service, self.__temp_service)
        aioble.register_services(self.__etat_service, self.__command_service)

    async def run(self):

        try:
            await self.__initialiser()
            print('BLE start')

            entretien_task = asyncio.create_task(self.entretien())
            update_etat_task = asyncio.create_task(self.update_etat_task())
            peripheral_task = asyncio.create_task(self.peripheral_task())
            command_set_task = asyncio.create_task(self.command_set_task())

            await asyncio.gather(entretien_task, update_etat_task, peripheral_task, command_set_task)
        except Exception as e:
            import sys
            sys.print_exception(e)
            print("Bluetooth non disponible")
            if not self.__optionnel:
                raise e

    async def entretien(self):
        try:
            self.load_profil_config()
        except Exception as e:
            print("Erreur load_profil_config")
            sys.print_exception(e)
        await asyncio.sleep(0)  # Yield

        await asyncio.sleep(30)

    async def update_etat_task(self):
        while True:
            self.update_etat()
            await asyncio.sleep_ms(5_000)

    def update_etat(self):
        # Mettre l'heure
        rtc = self.__runner.rtc_pret.is_set()
        time_val = time.time()
        # encoded_time = struct.pack('<BI', rtc, time_val)
        # self.__getetat_time_characteristic.write(encoded_time)

        # Mettre etat wifi
        status_1, status_2 = pack_info_wifi()
        # self.__getetat_wifi1_characteristic.write(status_1)
        # self.__getetat_wifi2_characteristic.write(status_2)
        status_wifi = status_1 + status_2
        self.__getetat_wifi_characteristic.write(status_wifi)

        # Remplir buffer lectures
        lectures_courantes = self.__runner.lectures_courantes
        # print("Lect courantes : %s" % lectures_courantes)

        valeurs_lectures = {}

        for key, value in lectures_courantes.items():
            did = key.split('/')[0]
            try:
                type_lecture = value['type']
                mapping_type = self.__devices_lecture_map[type_lecture]
                # print("BLE type lecture %s, mapping %s, did %s" % (type_lecture, mapping_type, did))
                try:
                    position_appareil = mapping_type.index(did)
                except ValueError:
                    i = 0
                    for map_value in mapping_type:
                        if did.startswith(map_value):
                            position_appareil = i
                            break
                        i += 1
                    else:
                        position_appareil = None

                if position_appareil is not None:
                    nom_valeur = '%s_%s' % (type_lecture, position_appareil)
                    valeurs_lectures[nom_valeur] = value['valeur']
            except (ValueError, KeyError):
                pass

        # print("BLE valeurs lectures mappees : ", valeurs_lectures)

        self.__lectures_sticky.update(valeurs_lectures)

        try:
            switch_1 = self.__lectures_sticky['switch_0'] == 1
        except KeyError:
            switch_1 = None
        try:
            switch_2 = self.__lectures_sticky['switch_1'] == 1
        except KeyError:
            switch_2 = None
        try:
            switch_3 = self.__lectures_sticky['switch_2'] == 1
        except KeyError:
            switch_3 = None
        try:
            switch_4 = self.__lectures_sticky['switch_3'] == 1
        except KeyError:
            switch_4 = None

        switch_encoding = pack_bools((
            switch_1 is not None, switch_1,
            switch_2 is not None, switch_2,
            switch_3 is not None, switch_3,
            switch_4 is not None, switch_4,
        ))

        try:
            temperature_1 = int(self.__lectures_sticky['temperature_0'] * 100)
        except (KeyError, TypeError, ValueError):
            temperature_1 = constantes.CONST_SHORT_MIN  # Minimum
        try:
            temperature_2 = int(self.__lectures_sticky['temperature_1'] * 100)
        except (KeyError, TypeError, ValueError):
            temperature_2 = constantes.CONST_SHORT_MIN  # Minimum
        try:
            humidite = int(self.__lectures_sticky['humidite_0'] * 10)
        except (KeyError, TypeError, ValueError):
            humidite = constantes.CONST_SHORT_MIN

        encoded_lectures = struct.pack('<BIhhhB', rtc, time_val, temperature_1, temperature_2, humidite, switch_encoding)
        self.__getetat_lectures_characteristic.write(encoded_lectures)

    async def peripheral_task(self):
        try:
            nom_appareil = get_nom_appareil()[0:25]
        except TypeError:
            nom_appareil = NOM_APPAREIL

        while True:
            try:
                print(const("BLE %s await connection") % nom_appareil)
                async with await aioble.advertise(
                    _ADV_INTERVAL_MS,
                    name=nom_appareil,
                    services=[_ENV_COMMAND_UUID],
                    appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER,
                ) as connection:
                    print("BLE connection from", connection.device)
                    await connection.disconnected(timeout_ms=600_000)
                    # await self.connection_thread(connection)
            except asyncio.CancelledError:
                print(const("BLE CancelledError"))
            finally:
                print(const("BLE disconnected"))

    # async def connection_thread(self, connection):
    #     try:
    #         print(const("BLE connection from"), connection.device)
    #         await connection.disconnected(timeout_ms=600_000)
    #     except asyncio.CancelledError:
    #         print(const("BLE CancelledError "), connection.device)
    #     finally:
    #         print(const("BLE disconnected "), connection.device)

    async def command_set_task(self):
        while True:
            try:
                await self.recevoir_config()
            except asyncio.TimeoutError:
                print("BLE timeout reception config")
            except KeyError:
                print("BLE config key manquante")
            except ValueError:
                print("BLE config trop long")

    async def recevoir_config(self):
        info_config = await recevoir_string(self.__command_write_characteristic, MAXLEN=200)
        print("Info config: %s" % info_config)
        params = json.loads(info_config)

        # Determiner commande
        commande = params['commande']

        if commande == 'setWifi':
            self.process_config_wifi(params)
        elif commande == 'setUser':
            self.process_config_user(params)
        elif commande == 'setRelai':
            self.process_config_relai(params)
        elif commande == 'setSwitch':
            await self.process_set_switch(params)
        else:
            print("BLE config inconnue %s" % commande)
            return

    def process_config_wifi(self, params):
        ssid = params['ssid']
        password = params['password']
        print("SSID: %s" % params['ssid'])
        print("Mot de passe: %s" % password)
        try:
            with open('wifi.new.json', 'rb') as fichier:
                wifi_dict = json.load(fichier)
        except OSError:
            wifi_dict = dict()

        try:
            ssids = wifi_dict['ssids']
            if len(ssids) > 5:
                print('Erreur, >5 wifi pending')
                return
        except KeyError:
            ssids = dict()
            wifi_dict['ssids'] = ssids

        ssids[ssid] = {'password': password}
        from time import time
        wifi_dict['maj'] = time()
        with open('wifi.new.json', 'wb') as fichier:
            json.dump(wifi_dict, fichier)

    def process_config_user(self, params):
        user_id = params['user_id']
        if user_id == '':
            user_id = None
        idmg = params.get('idmg')
        if idmg == '':
            idmg = None

        try:
            with open('user.json', 'rb') as fichier:
                existant = json.load(fichier)
        except OSError:
            existant = dict()

        # TODO - ajouter verification d'autorisation, bouton reset hardware, etc.
        if idmg:
            existant['idmg'] = idmg
        if user_id:
            existant['user_id'] = user_id

        # with open(constantes.CONST_PATH_USER_NEW, 'wb') as fichier:
        # TODO : ajouter securite pour changement d'usager
        with open(constantes.CONST_PATH_USER, 'wb') as fichier:
            json.dump(existant, fichier)

        print('user change pour %s' % existant)

        from millegrilles.webutils import reboot
        reboot(Exception('BLE change user'))

    def process_config_relai(self, params):
        relai = params['relai']
        print("Relai: %s" % relai)

        try:
            with open('relais.new.json', 'rb') as fichier:
                relais_new = json.load(fichier)
        except OSError:
            relais_new = dict()

        try:
            liste_relais = relais_new['relais']
        except KeyError:
            liste_relais = list()
            relais_new['relais'] = liste_relais

        if len(liste_relais) > 5:
            print("liste relais pleine")
            return

        if relai in liste_relais:
            print("relai deja dans la liste")
            return

        liste_relais.append(relai)

        with open('relais.new.json', 'wb') as fichier:
            json.dump(relais_new, fichier)

    async def process_set_switch(self, params):
        print("Set switch ", params)

    def load_profil_config(self):
        try:
            with open(constantes.CONST_PATH_USER) as fichier:
                config = json.load(fichier)

            try:
                idmg = config['idmg'].encode('utf-8')
                self.__getetat_idmg_characteristic.write(idmg)
            except KeyError:
                pass

            try:
                user_id = config['user_id'].encode('utf-8')
                self.__getetat_userid_characteristic.write(user_id)
            except KeyError:
                pass
        except OSError:
            pass  # Fichier n'existe pas


def _encode_temperature(temp_deg_c):
    """
    Helper to encode the temperature characteristic (sint16, hundredths of a degree).
    """
    temp = int(temp_deg_c * 100)
    if -27315 <= temp <= 32767:
        return struct.pack("<h", temp)
    raise ValueError('temp invalide')


def _encode_humidity(hum_pct):
    """ Helper to encode the humidity characteristic (sint16, tenths of a percent). """
    hum = int(hum_pct * 10)
    if 0 <= hum <= 100:
        return struct.pack("<h", hum)
    raise ValueError('pct invalide')


async def recevoir_string(characteristic, MAXLEN=200):
    connection, value = await characteristic.written()

    valeur_string = ''
    while value and value != b'\x00':
        valeur_string += value.decode('utf-8')
        if len(valeur_string) > MAXLEN:
            raise ValueError("len > %d" % MAXLEN)
        connection, value = await asyncio.wait_for(characteristic.written(), 1)

    return valeur_string


def pack_bools(bool_vals: tuple[bool]) -> int:
    """
    Pack jusqu'a 8 bools dans un seul byte
    """
    if len(bool_vals) > 8:
        raise ValueError('max 8 bools')

    val = 0x0
    position = 0

    for b in bool_vals:
        if b is True:  # Note : None et False donnent 0
            val |= 1 << position
        position += 1

    return val
