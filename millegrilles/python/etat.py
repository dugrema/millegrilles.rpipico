# Generateur d'etat interne
async def generer_etat():
    import wifi
    from mgmessages import signer_message
    etat = {
        'wifi': wifi.get_etat_wifi(),
        'temperature_interne': lire_temperature_interne(),
        'timeout_http': 20
    }
    return await signer_message(etat, domaine='SenseursPassifs', action='etatAppareil')


def lire_temperature_interne():
    import machine
    import utime

    sensor_temp = machine.ADC(4)
    conversion_factor = 3.3 / (65535)
    reading = sensor_temp.read_u16() * conversion_factor
    temperature = round(27 - (reading - 0.706)/0.001721, 1)
    
    return temperature
