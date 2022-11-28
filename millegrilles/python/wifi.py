import network
import uasyncio as asyncio


async def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # print("WLAN status : %d" % wlan.status())
    status = wlan.ifconfig()
    # print( 'ip = ' + status[0] )

    with open('wifi.txt', 'r') as fichier:
        ssid = fichier.readline().strip()
        password = fichier.readline().strip()

    try:
        wlan.connect(ssid, password)
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
