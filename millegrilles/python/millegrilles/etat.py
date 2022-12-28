from .mgmessages import signer_message

CONST_NB_LECTURES_TEMP = 10

# Generateur d'etat interne
async def generer_etat(timeout_http=60):
    import wifi
    import time
    timestamp = time.time()
    etat = {
        'lectures_senseurs': {
            'rp2pico/wifi': {
                'valeur_str': wifi.get_etat_wifi()['ip'],
                'timestamp': timestamp,
                'type': 'ip',
            },
            'rp2pico/temperature': {
                'valeur': await lire_temperature_interne(),
                'timestamp': timestamp,
                'type': 'temperature',
            }
        },
        'timeout_http': timeout_http,
    }
    return await signer_message(etat, domaine='SenseursPassifs', action='etatAppareil')


async def lire_temperature_interne():
    import machine
    import utime
    import uasyncio as asyncio

    sensor_temp = machine.ADC(4)
    temperature = 0.0
    conversion_factor = 3.3 / (65535)
    for _ in range(0, CONST_NB_LECTURES_TEMP):
        reading = sensor_temp.read_u16() * conversion_factor
        temperature += 27 - (reading - 0.706)/0.001721
        asyncio.sleep(0.05)

    temperature = round(temperature / CONST_NB_LECTURES_TEMP, 1)
    
    return temperature
