# Programme appareil millegrille
import uasyncio as asyncio
import ledblink
import ntptime
import sys
import time

import mgmessages

CONST_MODE_INIT = 1
CONST_MODE_RECUPERER_CA = 2
CONST_MODE_SIGNER_CERTIFICAT = 3
CONST_MODE_POLLING = 99

CONST_HTTP_TIMEOUT_DEFAULT = 60

PATH_FICHIER_CONN = 'conn.json'
PATH_FICHIER_IDMG = 'idmg.txt'
PATH_FICHIER_WIFI = 'wifi.txt'

mode_operation = 0


async def initialisation():
    """
    Mode initial si aucun parametres charges
    """
    await ledblink.led_executer_sequence([1,2], executions=None)


async def initialiser_wifi():
    import wifi
    wifi_ok = False
    for _ in range(0, 5):
        try:
            await wifi.connect_wifi()
            wifi_ok = True
        except (RuntimeError, OSError) as e:
            print("Wifi error %s" % e)
            await asyncio.sleep(3)
    if wifi_ok is False:
        raise RuntimeError('wifi')
            

async def get_idmg():
    with open(PATH_FICHIER_IDMG, 'r') as fichier:
        idmg = fichier.read()
    asyncio.sleep(0)  # Yield
    idmg = idmg.strip()
    return idmg


# Recuperer la fiche (CA, chiffrage, etc)
async def charger_fiche():
    import json
    import urequests

    await initialiser_wifi()

    try:
        fiche_url = get_url_relai() + '/fiche.json'
    except OSError:
        print("Fichier connexion absent")
        return

    # Downloader la fiche
    print("Recuperer fiche a %s" % fiche_url)
    reponse = urequests.get(fiche_url)
    await asyncio.sleep(0)  # Yield
    if reponse.status_code != 200:
        raise Exception("http %d" % reponse.status_code)
    fiche_json = reponse.json()
    print("Fiche recue")
    
    return fiche_json


def get_url_relai():
    import json
    with open(PATH_FICHIER_CONN, 'rb') as fichier:
        url_relai = json.load(fichier)['relai']
    return url_relai


def get_http_timeout():
    import json
    try:
        with open(PATH_FICHIER_CONN, 'rb') as fichier:
            return json.load(fichier)['polling_timeout']
    except Exception:
        pass
    
    return CONST_HTTP_TIMEOUT_DEFAULT


async def recuperer_ca():
    print("Init millegrille")
    idmg, fiche = await asyncio.gather(
        get_idmg(),
        charger_fiche(),
    )
    del fiche['_millegrille']
    
    if fiche['idmg'] != idmg:
        raise Exception('IDMG mismatch')
    
    print("IDMG OK : %s" % idmg)
    
    # Sauvegarder le certificat CA
    mgmessages.sauvegarder_ca(fiche['ca'], idmg)


async def init_cle_privee(force=False):
    import os
    try:
        os.stat(mgmessages.PATH_CLE_PRIVEE)
    except OSError:
        mgmessages.generer_cle_secrete()
        print("Cle privee initialisee")


async def signature_certificat():
    """
    Mode d'attente de signature de certificat
    """
    import message_inscription
    await initialiser_wifi()
    await init_cle_privee()
    
    await message_inscription.run_inscription(get_url_relai())


async def polling():
    """
    Main thread d'execution du polling/commandes
    """
    import polling_messages
    global mode_operation
    while mode_operation == CONST_MODE_POLLING:
        try:
            http_timeout = get_http_timeout()
            print("http timeout : %d" % http_timeout)
            await polling_messages.polling_thread(http_timeout)
        except Exception as e:
            print("Erreur polling")
            sys.print_exception(e)
            await ledblink.led_executer_sequence([2, 1], 2)
        asyncio.sleep(2)


async def entretien():
    """
    Thread d'entretient durant polling
    """
    global mode_operation
    wifi_ok = False
    ntp_ok = False
    
    while True:
        print("Entretien mode %d" % mode_operation)
        try:
            if mode_operation > 1:
                if wifi_ok is False:
                    print("Start wifi")
                    await initialiser_wifi()
                    wifi_ok = True
                    print("Wifi OK")
                
                if wifi_ok is True and ntp_ok is False:
                    print("NTP")
                    ntptime.settime()
                    ntp_ok = True
                    print("Time : ", time.gmtime())
            
            if mode_operation == CONST_MODE_POLLING:
                # Faire entretien
                pass
        except Exception as e:
            print("Erreur entretien: %s" % e)
        
        await asyncio.sleep(20)


async def detecter_mode_operation():
    # Si wifi.txt/idmg.txt manquants, on est en mode initial.
    import os
    try:
        os.stat(PATH_FICHIER_WIFI)
        os.stat(PATH_FICHIER_IDMG)
        os.stat(PATH_FICHIER_CONN)
    except:
        print("Mode initialisation")
        return CONST_MODE_INIT
    
    try:
        os.stat('certs/ca.der')
    except:
        print("Mode recuperer ca.der")
        return CONST_MODE_RECUPERER_CA
    
    try:
        os.stat("certs/cert.pem")
    except:
        print("Mode signer certificat")
        return CONST_MODE_SIGNER_CERTIFICAT

    return CONST_MODE_POLLING  # Mode polling


async def main():
    global mode_operation
    mode_operation = await detecter_mode_operation()
    print("Mode operation initial %d" % mode_operation)
    asyncio.create_task(entretien())
    await ledblink.led_executer_sequence([4], executions=1)
    while True:
        try:
            mode_operation = await detecter_mode_operation()
            print("Mode operation: %s" % mode_operation)

            if mode_operation == CONST_MODE_INIT:
                await initialisation()
            elif mode_operation == CONST_MODE_RECUPERER_CA:
                await recuperer_ca()
            elif mode_operation == CONST_MODE_SIGNER_CERTIFICAT:
                await signature_certificat()
            elif mode_operation == CONST_MODE_POLLING:
                await polling()
            else:
                print("Mode operation non supporte : %d" % mode_operation)
                await ledblink.led_executer_sequence([1,1], executions=None)
        except Exception as e:
            print("Erreur main")
            sys.print_exception(e)
        
        await ledblink.led_executer_sequence([1, 3], 4)


if __name__ == '__main__':
    asyncio.run(main())
