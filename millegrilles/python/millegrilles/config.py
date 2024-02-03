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
CONST_PATH_TZOFFSET = const('tzoffset.json')
CONST_PATH_SOLAIRE = const('solaire.json')
CONST_PATH_RELAIS = const('relais.json')

CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_CHARGER_URL_RELAIS = const(3)
CONST_MODE_SIGNER_CERTIFICAT = const(4)
CONST_MODE_POLLING = const(99)

CONST_HTTP_TIMEOUT_DEFAULT = const(60)

CONST_CHAMP_HTTP_INSTANCE = const('http_instance')

CONST_CHAMPS_SOLAIRE = const(('dawn', 'sunrise', 'noon', 'sunset', 'dusk'))
CONST_SOLAIRE_CHANGEMENT = const(120)

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

    for _ in range(0, 3):
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
        with open(CONST_PATH_TZOFFSET, 'rb') as fichier:
            return load(fichier)['timezone']
    except (KeyError, OSError, ValueError):
        return None


def get_tz_offset():
    try:
        with open(CONST_PATH_TZOFFSET, 'rb') as fichier:
            return load(fichier)['offset']
    except (KeyError, OSError, ValueError):
        return None


def get_timezone_transition():
    try:
        with open(CONST_PATH_TZOFFSET, 'rb') as fichier:
            info_tz = load(fichier)
        transition_time = info_tz['transition_time']
        transition_offset = info_tz['transition_offset']
        return transition_time, transition_offset
    except (KeyError, OSError, ValueError):
        pass

    return None, None


async def transition_timezone():
    """ Effectuer une transition de timezone """
    try:
        with open(CONST_PATH_TZOFFSET, 'rb') as fichier:
            info_tz = load(fichier)
        await sleep(0)

        # Extraire timezone et le nouvel offset a appliquer
        timezone = info_tz['timezone']
        transition_offset = info_tz['transition_offset']

        print("tz transition a %s" % transition_offset)

        # Ecraser l'information courante. Ceci supprime l'information de transition qui vient de prendre effet.
        await set_timezone_offset(transition_offset, timezone)
    except (KeyError, OSError, ValueError):
        pass


async def set_timezone_offset(offset, timezone=None, transition_time=None, transition_offset=None):
    print("Offset : %s" % offset)

    # Charger info, aucun write si information non changee
    try:
        with open(CONST_PATH_TZOFFSET, 'rb') as fichier:
            tz_courant = load(fichier)
    except (OSError, ValueError):
        print('tzoffset.json absent/invalide')
        diff = True
        tz_courant = dict()
    else:
        await sleep(0)
        diff = offset != tz_courant.get('offset')
        diff |= timezone and timezone != tz_courant.get('timezone')
        if transition_time and transition_offset:
            try:
                diff |= transition_time and transition_time != tz_courant.get('transition_time')
                diff |= transition_offset and transition_offset != tz_courant.get('transition_offset')
            except TypeError:
                diff = True

    if diff:
        print("overwrite %s" % CONST_PATH_TZOFFSET)
        with open(CONST_PATH_TZOFFSET, 'wb') as fichier:
            params = {
                'offset': offset,
                'timezone': timezone or tz_courant.get('timezone'),
                'transition_time': transition_time or tz_courant.get('transition_time'),
                'transition_offset': transition_offset or tz_courant.get('transition_offset')
            }
            dump(params, fichier)


def temps_liste_to_secs(temps_list: list):
    temps = temps_list[0] * 3600
    try:
        temps += temps_list[1] * 60
    except IndexError:
        pass
    try:
        temps += temps_list[2]
    except IndexError:
        pass
    return temps


async def set_horaire_solaire(solaire: dict):
    print("set solaire %s" % solaire)
    try:
        with open(CONST_PATH_SOLAIRE, 'rb') as fichier:
            solaire_courant = load(fichier)
    except OSError:
        # sauvegarder information directement
        with open(CONST_PATH_SOLAIRE, 'wb') as fichier:
            print("maj solaire(1)")
            dump(solaire, fichier)
        return

    # Comparer valeurs recues, eviter write IO si les changements sont mineurs pour reduire usure de la memoire flash
    val_max = 0
    for champ in CONST_CHAMPS_SOLAIRE:
        try:
            # Comparer la valeur courant a la valeur recue, obtenir difference absolue
            val = temps_liste_to_secs(solaire[champ]) + 86400
            val_courant = temps_liste_to_secs(solaire_courant[champ]) + 86400
            val = abs(val_courant - val)
        except KeyError:
            # Valeur manquante, forcer sauvegarde
            val_max = CONST_SOLAIRE_CHANGEMENT + 1
        else:
            val_max = max(val, val_max)

    if val_max > CONST_SOLAIRE_CHANGEMENT:  # Limite de 2 minutes pour changer le contenu
        with open(CONST_PATH_SOLAIRE, 'wb') as fichier:
            print("maj solaire(2) diff %d secs" % val_max)
            dump(solaire, fichier)


def get_horaire_solaire():
    try:
        with open(CONST_PATH_SOLAIRE, 'rb') as fichier:
            return load(fichier)
    except OSError:
        return


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
    # url_relais = [app['url'] for app in fiche['applications']['senseurspassifs_relai'] if app['nature'] == 'dns']

    app_instance_pathname = dict()
    for instance_id, app_params in fiche['applicationsV2']['senseurspassifs_relai']['instances'].items():
        try:
            app_instance_pathname[instance_id] = app_params['pathname']
            print("instance_id %s pathname %s" % (instance_id, app_params['pathname']))
        except KeyError:
            pass

    print("relais %d instances" % len(app_instance_pathname))

    url_relais = list()
    for instance_id, instance_params in fiche['instances'].items():
        try:
            pathname = app_instance_pathname[instance_id]
        except KeyError:
            continue  # Pas de path

        try:
            port = instance_params['ports']['https']
        except KeyError:
            port = 443

        try:
            for domaine in instance_params['domaines']:
                url_relais.append(f'https://{domaine}:{port}{pathname}')
        except KeyError:
            pass

    if len(url_relais) > 0:
        sauvegarder_relais_liste(url_relais)

    return url_relais


def sauvegarder_relais_liste(url_relais: list):
    info_relais = None
    try:
        with open(CONST_PATH_RELAIS) as fichier:
            info_relais = load(fichier)
    except (OSError, KeyError):
        print("%s non disponible" % CONST_PATH_RELAIS)

    # Verifier si le contenu a change
    change = False
    if info_relais is None:
        change = True
    elif len(info_relais['relais']) != len(url_relais):
        change = True
    else:
        for relai in url_relais:
            if relai not in info_relais['relais']:
                change = True

    if change:
        print('Sauvegarder %s maj' % CONST_PATH_RELAIS)
        try:
            with open(CONST_PATH_RELAIS, 'wb') as fichier:
                dump({'relais': url_relais}, fichier)
        except Exception as e:
            print('Erreur sauvegarde %s' % CONST_PATH_RELAIS)
            print_exception(e)
    else:
        print("Relais non changes")


def get_relais():
    try:
        with open(CONST_PATH_RELAIS, 'rb') as fichier:
            return load(fichier)['relais']
    except (OSError, KeyError):
        return
