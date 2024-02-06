import uasyncio as asyncio
import bluetooth
import aioble
import json
import struct
import sys
import time

from micropython import const
from millegrilles.message_inscription import NOM_APPAREIL
from millegrilles.wifi import pack_info_wifi


# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# org.bluetooth.characteristic.temperature
_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A6E)
# org.bluetooth.characteristic.humidity
_ENV_SENSE_HUM_UUID = bluetooth.UUID(0x2A6F)
# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)

# Service de configuration MilleGrilles
_ENV_CONFIG_UUID = bluetooth.UUID('7aac7580-88d7-480f-8a01-65406c2decaf')
_ENV_SETWIFI_WRITE_UUID = bluetooth.UUID('7aac7581-88d7-480f-8a01-65406c2decaf')
_ENV_SETRELAIS_WRITE_UUID = bluetooth.UUID('7aac7582-88d7-480f-8a01-65406c2decaf')
_ENV_SETUSER_WRITE_UUID = bluetooth.UUID('7aac7586-88d7-480f-8a01-65406c2decaf')

# Service d'etat appareil MilleGrille
_ENV_ETAT_UUID = bluetooth.UUID('7aac7590-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_USERID_UUID = bluetooth.UUID('7aac7591-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_IDMG_UUID = bluetooth.UUID('7aac7592-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_WIFI1_UUID = bluetooth.UUID('7aac7593-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_WIFI2_UUID = bluetooth.UUID('7aac7594-88d7-480f-8a01-65406c2decaf')
_ENV_ETAT_TIME_UUID = bluetooth.UUID('7aac7595-88d7-480f-8a01-65406c2decaf')

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = const(250_000)


class BluetoothHandler:
    """ Classe principale pour Bluetooth. Utiliser run(). """

    def __init__(self, runner):
        self.__runner = runner  # Appareil

        self.__temp_service = None
        self.__config_service = None
        self.__etat_service = None

        self.__temp_characteristic = None
        self.__hum_characteristic = None

        self.__setwifi_write_characteristic = None
        self.__setrelais_write_characteristic = None
        self.__setuser_write_characteristic = None

        self.__getetat_idmg_characteristic = None
        self.__getetat_userid_characteristic = None
        self.__getetat_wifi1_characteristic = None
        self.__getetat_wifi2_characteristic = None
        self.__getetat_time_characteristic = None

    async def __initialiser(self):
        self.preparer_gatt_server()
        await asyncio.sleep(0)  # Yield

        self.load_profil_config()
        await asyncio.sleep(0)  # Yield

    def preparer_gatt_server(self):
        # Register GATT server.
        self.__temp_service = aioble.Service(_ENV_SENSE_UUID)
        self.__temp_characteristic = aioble.Characteristic(
            self.__temp_service, _ENV_SENSE_TEMP_UUID, read=True, notify=True
        )
        self.__hum_characteristic = aioble.Characteristic(
            self.__temp_service, _ENV_SENSE_HUM_UUID, read=True, notify=True
        )

        # Config
        self.__config_service = aioble.Service(_ENV_CONFIG_UUID)
        self.__setwifi_write_characteristic = aioble.Characteristic(
            self.__config_service, _ENV_SETWIFI_WRITE_UUID, write=True, capture=True, notify=True
        )
        self.__setrelais_write_characteristic = aioble.Characteristic(
            self.__config_service, _ENV_SETRELAIS_WRITE_UUID, write=True, capture=True, notify=True
        )
        self.__setuser_write_characteristic = aioble.Characteristic(
            self.__config_service, _ENV_SETUSER_WRITE_UUID, write=True, capture=True, notify=True
        )

        # Etat
        self.__etat_service = aioble.Service(_ENV_ETAT_UUID)
        self.__getetat_idmg_characteristic = aioble.BufferedCharacteristic(
            self.__etat_service, _ENV_ETAT_IDMG_UUID, read=True, max_len=56
        )
        self.__getetat_userid_characteristic = aioble.BufferedCharacteristic(
            self.__etat_service, _ENV_ETAT_USERID_UUID, read=True, max_len=51
        )
        self.__getetat_wifi1_characteristic = aioble.Characteristic(
            self.__etat_service, _ENV_ETAT_WIFI1_UUID, read=True, notify=True
        )
        self.__getetat_wifi2_characteristic = aioble.Characteristic(
            self.__etat_service, _ENV_ETAT_WIFI2_UUID, read=True, notify=True
        )
        self.__getetat_time_characteristic = aioble.Characteristic(
            self.__etat_service, _ENV_ETAT_TIME_UUID, read=True, notify=True
        )

        aioble.register_services(self.__etat_service, self.__config_service, self.__temp_service)

    async def run(self):

        try:
            await self.__initialiser()

            entretien_task = asyncio.create_task(self.entretien())
            update_etat_task = asyncio.create_task(self.update_etat_task())
            peripheral_task = asyncio.create_task(self.peripheral_task())
            wifi_set_task = asyncio.create_task(self.wifi_set_task())
            relais_set_task = asyncio.create_task(self.relais_set_task())
            # get_profil_task = asyncio.create_task(self.get_profil_task())
            user_set_task = asyncio.create_task(self.user_set_task())

            await asyncio.gather(
                entretien_task, update_etat_task, peripheral_task,
                wifi_set_task, relais_set_task, user_set_task,
                # get_profil_task,
            )
        except Exception as e:
            import sys
            sys.print_exception(e)
            print("Bluetooth non disponible")

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
        encoded_time = struct.pack('<BI', rtc, time_val)
        self.__getetat_time_characteristic.write(encoded_time)

        # Mettre etat wifi
        status_1, status_2 = pack_info_wifi()
        self.__getetat_wifi1_characteristic.write(status_1)
        self.__getetat_wifi2_characteristic.write(status_2)

        # Lire senseurs (etat instantane)
        # TODO : Lire senseurs

    async def peripheral_task(self):
        while True:
            try:
                async with await aioble.advertise(
                    _ADV_INTERVAL_MS,
                    name=NOM_APPAREIL,
                    services=[_ENV_SENSE_UUID, _ENV_CONFIG_UUID],
                    appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER,
                ) as connection:
                    print("BLE connection from", connection.device)
                    await connection.disconnected(timeout_ms=20_000)
            except asyncio.CancelledError:
                print("BLE CancelledError")
            finally:
                print("BLE disconnected")

    async def wifi_set_task(self):
        while True:
            try:
                await self.recevoir_wifi()
            except asyncio.TimeoutError:
                print("BLE timeout reception ssid")
            except KeyError:
                print("BLE ssid/password manquant")
            except ValueError:
                print("BLE ssid trop long")

    async def recevoir_wifi(self):
        info_wifi = await recevoir_string(self.__setwifi_write_characteristic, MAXLEN=200)
        print("Info wifi: %s" % info_wifi)
        params = json.loads(info_wifi)
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

    async def relais_set_task(self):
        while True:
            try:
                info_relais = await recevoir_string(self.__setrelais_write_characteristic, MAXLEN=1024)
                print("Info relais: %s" % info_relais)
                params = json.loads(info_relais)
                print("Relais: %s" % params.get('relais'))
            except asyncio.TimeoutError:
                print("Timeout reception relais")
            except ValueError:
                print("relais trop long")

    async def user_set_task(self):
        while True:
            try:
                await self.changer_usager()
            except asyncio.TimeoutError:
                print("Timeout reception relais")
            except ValueError:
                print("relais trop long")

    async def changer_usager(self):
        info_user = await recevoir_string(self.__setuser_write_characteristic, MAXLEN=200)
        print("Info user: %s" % info_user)
        params = json.loads(info_user)
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

        with open('user.json', 'wb') as fichier:
            json.dump(existant, fichier)

        print('user change pour %s' % existant)

    # async def get_profil_task(self):
    #     while True:
    #         # connection, value = await self.__getprofil_config_characteristic.written()
    #         await self.__getprofil_config_characteristic.written()
    #
    #         with open('conn.json', 'rb') as fichier:
    #             contenu = fichier.read()
    #
    #         while len(contenu) > 0:
    #             slice_contenu = contenu[0:20]
    #             contenu = contenu[20:]
    #             print('Profil : %s' % contenu)
    #
    #             self.__getprofil_config_characteristic.write(slice_contenu, send_update=True)
    #
    #             # Donner 3ms au client pour lire le buffer
    #             await asyncio.sleep_ms(3)
    #
    #         # Indiqer qu'il ne reste rien a recevoir
    #         print("profil termine")
    #         self.__getprofil_config_characteristic.write(b'\x00', send_update=True)

    def load_profil_config(self):
        try:
            with open('conn.json') as fichier:
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
