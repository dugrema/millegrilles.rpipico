from json import load, loads, dump, dumps
from os import stat
from uasyncio import sleep, sleep_ms
from sys import print_exception
from gc import collect

from millegrilles import urequests2 as requests
from millegrilles import wifi
from millegrilles.wifi import connect_wifi
from millegrilles.mgmessages import verifier_message, signer_message

CONST_PATH_FICHIER_CONN = const('conn.json')
CONST_PATH_FICHIER_DISPLAY = const('displays.json')
CONST_PATH_TIMEINFO = const('timeinfo')

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
            

async def recuperer_ca(buffer=None):
    from millegrilles.certificat import sauvegarder_ca
    
    print("Init millegrille")
    idmg = get_idmg()
    fiche = await charger_fiche(no_validation=True, buffer=buffer)
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


def get_timezone():
    try:
        with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
            return load(fichier)['timezone']
    except KeyError:
        return None


async def get_timezone_offset(self):
    try:
        if self.__timezone_offset is None:
            self.__timezone_offset = await charger_timeinfo(self.__url_relai_courant)
            if self.__timezone_offset is None:
                self.__timezone_offset = False  # Desactiver chargement
    except Exception as e:
        print("Erreur chargement timezone")
        sys.print_exception(e)
        e = None

def set_configuration_display(configuration: dict):
    # print('Maj configuration display')
    with open(CONST_PATH_FICHIER_DISPLAY, 'wb') as fichier:
        dump(configuration, fichier)


async def charger_fiche(ui_lock=None, no_validation=False, buffer=None):
    try:
        fiche_url = get_url_instance() + '/fiche.json'
        print("Charger fiche via %s" % fiche_url)
    except OSError:
        print("Fichier connexion absent")
        return

    # Downloader la fiche
    # print("Recuperer fiche a %s" % fiche_url)
    fiche_json = None
    reponse = await requests.get(fiche_url, lock=ui_lock)
    try:
        await sleep_ms(1)  # Yield
        if reponse.status_code != 200:
            raise Exception("fiche http status:%d" % reponse.status_code)
        
        await reponse.read_text_into(buffer)
        
    except Exception as e:
        print('Erreur chargement fiche')
        print_exception(e)
        return None
    finally:
        print("charger_fiche fermer reponse")
        reponse.close()
        reponse = None

        # Cleanup memoire
        collect()
        await sleep_ms(1)  # Yield

    fiche_json = loads(buffer.get_data())
    
    print("Fiche recue\n%s" % fiche_json)
    if no_validation is True:
        return fiche_json

    info_cert = await verifier_message(fiche_json)
    if 'core' in info_cert['roles']:
        return fiche_json
    
    return None


# Recuperer la fiche (CA, chiffrage, etc)
async def charger_relais(ui_lock=None, refresh=False, buffer=None):
    info_relais = None
    try:
        with open('relais.json') as fichier:
            info_relais = load(fichier)
            if refresh is False:
                return info_relais['relais']
    except (OSError, KeyError):
        print("relais.json non disponible")
    
    fiche_json = await charger_fiche(ui_lock, buffer=buffer)
    if fiche_json is not None:
        url_relais = [app['url'] for app in fiche_json['applications']['senseurspassifs_relai'] if app['nature'] == 'dns']
        
        if info_relais is None or info_relais['relais'] != url_relais:
            print('Sauvegarder relais.json maj')
            try:
                with open('relais.json', 'wb') as fichier:
                    dump({'relais': url_relais}, fichier)
            except Exception as e:
                print('Erreur sauvegarde relais.json')
                print_exception(e)
        
        return url_relais
        
    return None


async def generer_message_timeinfo(timezone_str: str):
    # Generer message d'inscription
    message_inscription = {
        "timezone": timezone_str,
    }
    message_inscription = await signer_message(message_inscription, action='getTimezoneInfo')
    
    # Garbage collect
    await sleep_ms(200)
    collect()
    await sleep_ms(1)

    return message_inscription


async def charger_timeinfo(url_relai: str, buffer, refresh: False):
    
    offset_info = None
    try:
        with open('tzoffset.json', 'rb') as fichier:
            offset_info = load(fichier)
            if refresh is False:
                return offset_info['offset']
    except OSError:
        print('tzoffset.json absent')
    except KeyError:
        print('tzoffset.json erreur contenu')
    
    print("Charger information timezone %s" % url_relai)
    timezone_str = get_timezone()
    if timezone_str is not None:
        buffer.set_text(dumps(await generer_message_timeinfo(timezone_str)))
        
        await sleep_ms(1)  # Yield
        collect()
        await sleep_ms(1)  # Yield
        
        reponse = await requests.post(
            url_relai + '/' + CONST_PATH_TIMEINFO,
            data=buffer.get_data(),
            headers={'Content-Type': 'application/json'}
        )

        try:
            await reponse.read_text_into(buffer)
            reponse = None

            await sleep_ms(1)  # Yield
            collect()
            await sleep_ms(1)  # Yield

            # data = await reponse.json()
            data = loads(buffer.get_data())
            offset = data['timezone_offset']
            print("Offset : %s" % offset)
            
            if offset_info is None or offset_info['offset'] != offset:
                with open('tzoffset.json', 'wb') as fichier:
                    dump({'offset': offset}, fichier)
            
            return offset
        except KeyError:
            return None
        finally:
            if reponse is not None:
                reponse.close()
    else:
        if offset_info is None:
            with open('tzoffset.json', 'wb') as fichier:
                dump({'offset': 0}, fichier)
        
