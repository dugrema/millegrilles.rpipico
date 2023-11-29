from json import load, loads, dump, dumps
from os import stat
from uasyncio import sleep, sleep_ms
from sys import print_exception
from gc import collect

from mgutils import comparer_dict
from millegrilles.const_leds import CODE_CONFIG_INITIALISATION
from millegrilles.ledblink import led_executer_sequence
from millegrilles.wifi import connect_wifi
from millegrilles.certificat import PATH_CERT, PATH_CA_CERT

CONST_PATH_FICHIER_CONN = const('conn.json')
CONST_PATH_FICHIER_DISPLAY = const('displays.json')
CONST_PATH_FICHIER_PROGRAMMES = const('programmes.json')
CONST_PATH_TIMEINFO = const('timeinfo')

CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_CHARGER_URL_RELAIS = const(3)
CONST_MODE_SIGNER_CERTIFICAT = const(4)
CONST_MODE_POLLING = const(99)

CONST_HTTP_TIMEOUT_DEFAULT = const(60)

CONST_CHAMP_HTTP_INSTANCE = const('http_instance')

async def detecter_mode_operation():
    # Si wifi.txt/idmg.txt manquants, on est en mode initial.
    try:
        stat(CONST_PATH_FICHIER_CONN)
    except:
        print("Mode initialisation")
        return CONST_MODE_INIT
    
    try:
        stat(PATH_CA_CERT)
    except:
        print("Mode recuperer ca.der")
        return CONST_MODE_RECUPERER_CA
    
    try:
        stat(PATH_CERT)
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


def get_tz_offset():
    try:
        with open('tzoffset.json', 'rb') as fichier:
            offset_info = load(fichier)
        return offset_info['offset']
    except (KeyError, OSError):
        return None


# async def get_timezone_offset(self):
#     try:
#         if self.__timezone_offset is None:
#             self.__timezone_offset = await charger_timeinfo(self.__url_relai_courant)
#             if self.__timezone_offset is None:
#                 self.__timezone_offset = False  # Desactiver chargement
#     except Exception as e:
#         print("Erreur chargement timezone")
#         sys.print_exception(e)
#         e = None


async def set_timezone_offset(offset, timezone=None):
    print("Offset : %s" % offset)

    # Charger info, aucun write si information non changee
    offset_info = None
    try:
        with open('tzoffset.json', 'rb') as fichier:
            offset_info = load(fichier)
        timezone_courant = offset_info.get('timezone')
    except OSError:
        print('tzoffset.json absent')
        timezone_courant = None

    if offset_info is None or offset_info['offset'] != offset:
        params = {'offset': offset, 'timezone': timezone_courant}
        if timezone is not None:  # Override timezone
            params['timezone'] = timezone
        with open('tzoffset.json', 'wb') as fichier:
            dump(params, fichier)


def set_configuration_display(configuration: dict):
    # print('Maj configuration display')
    with open(CONST_PATH_FICHIER_DISPLAY, 'wb') as fichier:
        dump(configuration, fichier)


async def update_configuration_programmes(configuration: dict, appareil):
    """
    Detecte les programmes changes et sauvegarde programmes.json
    @return Liste des programmes changes
    """
    try:
        with open(CONST_PATH_FICHIER_PROGRAMMES, 'r') as fichier:
            existant = load(fichier)
    except OSError:
        # Fichier inexistant
        set_configuration_programmes(configuration)
        existant = dict()

    # Detecter quels programmes ont changes
    fichier_dirty = False
    for prog_id, programme in configuration.items():
        changement = True
        if existant.get(prog_id) is not None:
            # Detecter changements au programme existant
            changement = not comparer_dict(existant[prog_id], programme)

            if changement is False:
                print("Programme %s - aucun changement" % prog_id)
                # Skip ajouter_programme, aucun changement
            else:
                print("Programme %s - changements detectes" % prog_id)
                print("Ancien %s" % existant[prog_id])
                print("Nouveau %s" % programme)
                print("---\n")

            del existant[prog_id]

        if changement is True:
            # Ajouter/modifier programme
            try:
                await appareil.ajouter_programme(programme)
            except Exception as e:
                print("Erreur ajout programme %s" % prog_id)
                print_exception(e)
            fichier_dirty = True
    
    # Supprimer tous les programmes existants non listes
    for programme_id in existant.keys():
        try:
            await appareil.supprimer_programme(programme_id)
        except Exception as e:
            print("Erreur retrait programme %s" % programme_id)
            print_exception(e)
        fichier_dirty = True
    
    if fichier_dirty is True:
        # Si au moins un changement, on sauvegarde le fichier complet
        print("Sauvegarder programmes.json")
        set_configuration_programmes(configuration)
    

def set_configuration_programmes(configuration: dict):
    with open(CONST_PATH_FICHIER_PROGRAMMES, 'wb') as fichier:
        dump(configuration, fichier)
    

def sauvegarder_relais(fiche: dict):
    url_relais = [app['url'] for app in fiche['applications']['senseurspassifs_relai'] if app['nature'] == 'dns']
    sauvegarder_relais_liste(url_relais)
    return url_relais


def sauvegarder_relais_liste(url_relais: list):
    info_relais = None
    try:
        with open('relais.json') as fichier:
            info_relais = load(fichier)
    except (OSError, KeyError):
        print("relais.json non disponible")

    if info_relais is None or info_relais['relais'] != url_relais:
        print('Sauvegarder relais.json maj')
        try:
            with open('relais.json', 'wb') as fichier:
                dump({'relais': url_relais}, fichier)
        except Exception as e:
            print('Erreur sauvegarde relais.json')
            print_exception(e)

