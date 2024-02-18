import network
import struct
import uasyncio as asyncio
import time

from gc import collect
from sys import print_exception
from micropython import const

from millegrilles.constantes import CONST_CHAMP_WIFI_SSID, CONST_CHAMP_WIFI_CHANNEL, CONST_UTF8, CONST_CHAMP_IP
from . import uping


CONST_EXPIRATION_ERREUR = const(10 * 60)  # Expiration apres une deconnexion


class StatusWifi:

    def __init__(self):
        self.connecte = False
        self.ip = None
        self.last_ping_ok = None

    async def wifi_thread(self):
        while True:
            await self.is_wifi_ok()
            await asyncio.sleep(60)

    async def is_wifi_ok(self):
        """ Verifier etat avec antenne """
        wlan = network.WLAN(network.STA_IF)

        self.connecte = wlan.isconnected()
        if self.connecte is False:
            return False

        status = wlan.status()
        if status != 3:
            return False

        # Ping gateway, timeout court (la connexion est directe)
        gw_ip = wlan.ifconfig()[2]
        collect()
        await asyncio.sleep(0)  # Yield
        timeout = 25  # Besoin d'un minimum de 11ms pour transmettre le paquet et recevoir reponse
        for _ in range(0, 10):
            # print(const("ping timeout %d ms" % timeout))
            try:
                res = uping.ping(gw_ip, count=1, timeout=timeout, quiet=True)
                if res[1] == 1:  # Ping reussi
                    break
                timeout += 25  # Augmenter timeout
            except MemoryError as e:
                await asyncio.sleep(0)  # Yield
                collect()
                await asyncio.sleep(0)  # Yield
                print_exception(e)

            # Reessayer
            await asyncio.sleep_ms(200)
        else:
            res = (0, 0)  # Valeur par defaut (echec)

        await asyncio.sleep(0)  # Yield
        collect()
        await asyncio.sleep(0)  # Yield

        # Verifier qu'au moins 1 paquet a ete recu (confirme par gateway)
        if res[1] == 0:
            print(const("is_wifi_ok : Ping gateway (%s) failed") % gw_ip)
            return False  # Ping succes, connexion WIFI fonctionne

        # La connexion WIFI est OK
        self.last_ping_ok = time.time()
        return True

    def err_expire(self):
        """ @returns True si la connexion ne fonctionne plus depuis un certain temps. """
        if self.last_ping_ok is None:
            # La connexion n'a jamais ete etablie
            return False

        return time.time() - self.last_ping_ok > CONST_EXPIRATION_ERREUR

    @property
    def ok(self):
        return self.last_ping_ok and time.time() - self.last_ping_ok < CONST_EXPIRATION_ERREUR


def detecter_wifi():
    from network import WLAN, STA_IF
    wlan = WLAN(STA_IF)
    scan_result = wlan.scan()

    # Champs : ssid, bssid, channel, rssi, security, hidden
    # Trier par force du signal (RSSI inv)
    scan_result.sort(key=lambda x: x[3], reverse=True)

    return scan_result


async def connect_wifi(ssid: str, password: str, tentatives=3):
    from gc import collect

    CONST_SSID_MANQUANT = const('SSID manquant')
    CONST_PASSWORD_MANQUANT = const('password manquant')
    CONST_WIFI_CONNECT_TO = const('WIFI connect to %s')
    CONST_WIFI_ATTENDRE = const('WIFI connect to %s')
    CONST_WIFI_STATUS_FAILED = const("WLAN status %s, connection failed on %s")
    CONST_WIFI_ERR1 = const("non connecte")

    # print("connect_wifi ssid %s pass %s" % (ssid, password))
    if not isinstance(ssid, str) or ssid == '':
        raise ValueError(CONST_SSID_MANQUANT)
    if not isinstance(password, str) or ssid == '':
        raise ValueError(CONST_PASSWORD_MANQUANT)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Cleanup
    wlan.disconnect()
    await asyncio.sleep(0)
    collect()
    await asyncio.sleep_ms(200)

    for _ in range(0, tentatives):
        try:
            print(CONST_WIFI_CONNECT_TO % ssid)
            wlan.connect(ssid, password)
        except OSError as e:
            if e.errno == 1:
                wlan.active(True)
                continue
            else:
                raise e

        # Wait for connect or fail
        print(CONST_WIFI_ATTENDRE % ssid)
        max_wait = 20  # 20 secondes, si echec la connexion retry immediatement
        status = network.STAT_CONNECTING
        while max_wait > 0 and status == network.STAT_CONNECTING:
            # print("%s : attendre - reste %d secs" % (ssid, max_wait))
            await asyncio.sleep(1)
            # Update status
            status = wlan.status()
            max_wait -= 1

        if wlan.status() == network.STAT_GOT_IP:
            ip = wlan.ifconfig()[0]
            return ip
        else:
            # print("WLAN Status %s" % wlan.status())
            print(CONST_WIFI_STATUS_FAILED % (wlan.status(), ssid))

    raise ErreurConnexionWifi(CONST_WIFI_ERR1)


def get_etat_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    status = wlan.ifconfig()

    return {CONST_CHAMP_IP: status[0]}


def map_ip_bytes(ip):
    return bytes(map(int, (ip).split('.')))


def get_wifi_detail():
    wlan = network.WLAN(network.STA_IF)
    connected = wlan.isconnected()
    status = wlan.status()
    ssid = wlan.config(CONST_CHAMP_WIFI_SSID)
    channel = wlan.config(CONST_CHAMP_WIFI_CHANNEL)
    ifconfig = wlan.ifconfig()
    client_ip, client_mask, gw_ip, dns_ip = ifconfig
    return connected, status, ssid, channel, client_ip, client_mask, gw_ip, dns_ip


def pack_info_wifi():
    val = get_wifi_detail()
    connected, status, ssid, channel, client_ip, client_mask, gw_ip, dns_ip = val
    vals = [connected, status, channel, map_ip_bytes(client_ip), map_ip_bytes(client_mask), map_ip_bytes(gw_ip), map_ip_bytes(dns_ip)]
    CHAMP_PACK_WIFI = const('<BBB4s4s4s4s')
    status_1 = struct.pack(CHAMP_PACK_WIFI, *vals)
    status_2 = ssid.encode(CONST_UTF8)[:20]
    return status_1, status_2


class ErreurConnexionWifi(Exception):
    pass
