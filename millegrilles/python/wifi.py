import json
import network
import uasyncio as asyncio


PATH_CONFIGURATION = const('conn.json')


async def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # print("WLAN status : %d" % wlan.status())
    status = wlan.ifconfig()
    # print( 'ip = ' + status[0] )

    #with open('wifi.txt', 'r') as fichier:
    #    ssid = fichier.readline().strip()
    #    password = fichier.readline().strip()

    with open(PATH_CONFIGURATION, 'rb') as fichier:
        config = json.load(fichier)

    try:
        wlan.connect(config['wifi_ssid'], config['wifi_password'])
    except KeyError as e:
        raise Exception('SSID/password manquant')
    except OSError as e:
        if e.errno == 1:
            toggle(wlan)
        else:
            raise e

    # Wait for connect or fail
    max_wait = 20
    while max_wait > 0:

        if wlan.status() < -1 or wlan.status() >= 3:
            break

        max_wait -= 1
        # print('waiting for connection...')
        asyncio.sleep(1)
        
    # Handle connection error
    if wlan.status() != 3:
        # print("WLAN Status %s" % wlan.status())
        raise RuntimeError('network connection failed')
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
    