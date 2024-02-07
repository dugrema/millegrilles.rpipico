import json
import network
import struct
import uasyncio as asyncio

from . import uping
from micropython import const

from millegrilles.constantes import CONST_CHAMP_WIFI_SSID, CONST_CHAMP_WIFI_CHANNEL, CONST_UTF8, CONST_CHAMP_IP


PATH_CONFIGURATION = const('conn.json')


async def connect_wifi(liste_wifi: list, tentatives=3):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Cleanup
    wlan.disconnect()
    await asyncio.sleep_ms(200)

    for config in liste_wifi:
        for t in range(0, tentatives):
            try:
                ssid = config['wifi_ssid']
                print("WiFI connect to %s" % ssid)
                wlan.connect(ssid, config['wifi_password'])
            except KeyError as e:
                # raise Exception('SSID/password manquant')
                print("Config SSID/password manquant, skip")
                continue
            except OSError as e:
                if e.errno == 1:
                    wlan.active(True)
                    continue
                else:
                    raise e

            # Wait for connect or fail
            print("Attendre connexion WIFI a %s" % ssid)
            max_wait = 20  # 20 secondes, si echec la connexion retry immediatement
            status = network.STAT_CONNECTING
            while max_wait > 0 and status == network.STAT_CONNECTING:
                print("%s : attendre - reste %d secs" % (ssid, max_wait))
                status = wlan.status()
                if status == network.STAT_GOT_IP:
                    print('WIFI ready')
                    break
                # if status < -1 or status >= 3:
                #     print("Break, status %d" % status)
                #     break
                max_wait -= 1
                await asyncio.sleep(1)

            # Handle connection error
            if wlan.status() != network.STAT_GOT_IP:
                print("WLAN Status %s" % wlan.status())
                # raise RuntimeError('network connection failed')
                print("WLAN connection failed on %s" % ssid)
            else:
                #print('connected')
                status = wlan.ifconfig()
                # print( 'ip = ' + status[0] )
                return status


def get_etat_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    status = wlan.ifconfig()
    
    return {CONST_CHAMP_IP: status[0]}


def is_wifi_ok():
    wlan = network.WLAN(network.STA_IF)

    if wlan.isconnected() is False:
        return False

    status = wlan.status()
    if status != 3:
        return False

    # Ping gateway, 1 seul paquet avec timeout court (la connexion est directe)
    gw_ip = wlan.ifconfig()[2]
    res = uping.ping(gw_ip, count=1, timeout=100, quiet=True)

    # Verifier qu'au moins 1 paquet a ete recu (confirme par gateway)
    if res[1] > 0:
        return True  # Ping succes, connexion WIFI fonctionne
    print(const("is_wifi_ok : Ping gateway (%s) failed") % gw_ip)

    return False


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
