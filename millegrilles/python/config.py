from json import load
from os import stat
from wifi import connect_wifi
from uasyncio import sleep
from sys import print_exception

import urequests2 as requests

import wifi

CONST_PATH_FICHIER_CONN = const('conn.json')

CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_CHARGER_URL_RELAIS = const(3)
CONST_MODE_SIGNER_CERTIFICAT = const(4)
CONST_MODE_POLLING = const(99)

CONST_CHAMP_HTTP_INSTANCE = const('http_instance')

async def detecter_mode_operation():
    # Si wifi.txt/idmg.txt manquants, on est en mode initial.
    try:
        stat(CONST_PATH_FICHIER_CONN)
    except:
        print("Mode initialisation")
        return CONST_MODE_INIT
    
    try:
        stat('certs/ca.der')
    except:
        print("Mode recuperer ca.der")
        return CONST_MODE_RECUPERER_CA
    
    try:
        stat("certs/cert.pem")
    except:
        print("Mode signer certificat")
        return CONST_MODE_SIGNER_CERTIFICAT

    return CONST_MODE_POLLING  # Mode polling


async def initialisation():
    """
    Mode initial si aucun parametres charges
    """
    await led_executer_sequence(CODE_CONFIG_INITIALISATION, executions=None)


async def initialiser_wifi():
    wifi_ok = False
    
    try:
        with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
            wifis = load(fichier)['wifis']
    except KeyError:
        try:
            with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
                config_conn = load(fichier)
                wifi_ssid = config_conn['wifi_ssid']
                wifi_password = config_conn['wifi_password']
                config_conn = None
                wifis = [{'wifi_ssid': wifi_ssid, 'wifi_password': wifi_password}]
        except KeyError:
            # Aucune configuration wifi
            raise RuntimeError('wifi')

    for _ in range(0, 5):
        try:
            status = await connect_wifi(wifis)
            return status
        except (RuntimeError, OSError) as e:
            print("Wifi error %s" % e)
            await sleep(3)
        except Exception as e:
            print("connect_wifi exception")
            print_exception(e)
    
    if wifi_ok is False:
        raise RuntimeError('wifi')
            

async def recuperer_ca():
    from certificat import sauvegarder_ca
    
    print("Init millegrille")
    idmg = get_idmg()
    fiche = await charger_fiche()
    del fiche['_millegrille']
    
    if fiche['idmg'] != idmg:
        raise Exception('IDMG mismatch')
    
    print("IDMG OK : %s" % idmg)
    
    # Sauvegarder le certificat CA
    sauvegarder_ca(fiche['ca'], idmg)


#async def init_cle_privee(force=False):
#    from certificat import PATH_CLE_PRIVEE, generer_cle_secrete
#    try:
#        stat(PATH_CLE_PRIVEE)
#    except OSError:
#        generer_cle_secrete()
#        print("Cle privee initialisee")


def get_url_instance():
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return load(fichier)[CONST_CHAMP_HTTP_INSTANCE]


def get_http_timeout():
    try:
        with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
            return load(fichier)['http_timeout']
    except Exception:
        pass
    
    return CONST_HTTP_TIMEOUT_DEFAULT


def get_idmg():
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return load(fichier)['idmg']


def get_user_id():
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return load(fichier)['user_id']


# Recuperer la fiche (CA, chiffrage, etc)
async def charger_fiche():
    try:
        fiche_url = get_url_instance() + '/fiche.json'
    except OSError:
        print("Fichier connexion absent")
        return

    # Downloader la fiche
    # print("Recuperer fiche a %s" % fiche_url)
    fiche_json = None
    reponse = await requests.get(fiche_url)
    try:
        await sleep(0)  # Yield
        if reponse.status_code != 200:
            raise Exception("fiche http status:%d" % reponse.status_code)
        fiche_json = await reponse.json()
        # print("Fiche recue\n%s" % fiche_json)
    finally:
        print("charger_fiche fermer reponse")
        reponse.close()
        
    return fiche_json
