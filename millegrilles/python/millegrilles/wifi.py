import json
import network
import uasyncio as asyncio
from . import uping


PATH_CONFIGURATION = const('conn.json')


async def connect_wifi(liste_wifi: list):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    status = wlan.ifconfig()

    # Cleanup
    wlan.disconnect()
    asyncio.sleep_ms(200)

    tentatives = 3
    for t in range(0, tentatives):
        for config in liste_wifi:
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
            max_wait = 7
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
    
    return {'ip': status[0]}


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
    print("is_wifi_ok : Ping gateway (%s) failed" % gw_ip)

    return False
    