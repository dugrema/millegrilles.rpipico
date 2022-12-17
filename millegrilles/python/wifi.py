import json
import network
import uasyncio as asyncio


PATH_CONFIGURATION = const('conn.json')


async def connect_wifi(liste_wifi: list):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    status = wlan.ifconfig()

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
        max_wait = 30
        while max_wait > 0:
            print("Attendre - reste %d secs" % max_wait)
            if wlan.status() < -1 or wlan.status() >= 3:
                print("Break, status %d" % wlan.status())
                break
            max_wait -= 1
            await asyncio.sleep(1)
            
        # Handle connection error
        if wlan.status() != 3:
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
    status = wlan.status()
    if status == 3:
        return True
    return False
    