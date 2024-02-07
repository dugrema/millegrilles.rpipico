from json import load, dump
from os import stat, unlink
from uasyncio import sleep, sleep_ms
from sys import print_exception

from mgutils import comparer_dict
from millegrilles.const_leds import CODE_CONFIG_INITIALISATION
from millegrilles.ledblink import led_executer_sequence
from millegrilles.wifi import connect_wifi
from millegrilles.certificat import PATH_CERT, PATH_CA_CERT

from millegrilles.constantes import CONST_PATH_FICHIER_CONN, CONST_PATH_FICHIER_DISPLAY, CONST_PATH_FICHIER_PROGRAMMES, \
    CONST_PATH_TIMEINFO, CONST_PATH_TZOFFSET, CONST_PATH_SOLAIRE, CONST_PATH_RELAIS, CONST_PATH_RELAIS_NEW, \
    CONST_MODE_INIT, CONST_MODE_RECUPERER_CA, CONST_MODE_CHARGER_URL_RELAIS, CONST_MODE_SIGNER_CERTIFICAT, \
    CONST_MODE_POLLING, CONST_HTTP_TIMEOUT_DEFAULT, CONST_CHAMP_HTTP_INSTANCE, \
    CONST_CHAMPS_SOLAIRE, CONST_SOLAIRE_CHANGEMENT, \
    CONST_CHAMP_HTTP_TIMEOUT, \
    CONST_CHAMP_IDMG, CONST_CHAMP_USER_ID, CONST_CHAMP_TIMEZONE, CONST_CHAMP_OFFSET, \
    CONST_CHAMP_TRANSITION_TIME, CONST_CHAMP_TRANSITION_OFFSET, \
    CONST_CHAMP_APPLICATIONSV2, CONST_CHAMP_SENSEURSPASSIFS_RELAI, CONST_CHAMP_INSTANCES, CONST_CHAMP_PATHNAME, \
    CONST_CHAMP_HTTPS, CONST_CHAMP_PORTS, CONST_CHAMP_DOMAINES, CONST_CHAMP_RELAIS, \
    CONST_READ_BINARY, CONST_WRITE_BINARY


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
        with open(CONST_PATH_FICHIER_CONN, CONST_READ_BINARY) as fichier:
            wifis = load(fichier)['wifis']
    except KeyError:
        try:
            with open(CONST_PATH_FICHIER_CONN, CONST_READ_BINARY) as fichier:
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
            

# def get_url_instance():
#     with open(CONST_PATH_FICHIER_CONN, CONST_READ_BINARY) as fichier:
#         return load(fichier)[CONST_CHAMP_HTTP_INSTANCE]


def get_http_timeout():
    try:
        with open(CONST_PATH_FICHIER_CONN, CONST_READ_BINARY) as fichier:
            return load(fichier)[CONST_CHAMP_HTTP_TIMEOUT]
    except Exception:
        pass
    
    return CONST_HTTP_TIMEOUT_DEFAULT


def get_idmg():
    with open(CONST_PATH_FICHIER_CONN, CONST_READ_BINARY) as fichier:
        return load(fichier)[CONST_CHAMP_IDMG]


def get_user_id():
    with open(CONST_PATH_FICHIER_CONN, CONST_READ_BINARY) as fichier:
        return load(fichier)[CONST_CHAMP_USER_ID]


def get_timezone():
    try:
        with open(CONST_PATH_TZOFFSET, CONST_READ_BINARY) as fichier:
            return load(fichier)[CONST_CHAMP_TIMEZONE]
    except (KeyError, OSError, ValueError):
        return None


def get_tz_offset():
    try:
        with open(CONST_PATH_TZOFFSET, CONST_READ_BINARY) as fichier:
            return load(fichier)[CONST_CHAMP_OFFSET]
    except (KeyError, OSError, ValueError):
        return None


def get_timezone_transition():
    try:
        with open(CONST_PATH_TZOFFSET, CONST_READ_BINARY) as fichier:
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
        with open(CONST_PATH_TZOFFSET, CONST_READ_BINARY) as fichier:
            info_tz = load(fichier)
        await sleep(0)

        # Extraire timezone et le nouvel offset a appliquer
        timezone = info_tz[CONST_CHAMP_TIMEZONE]
        transition_offset = info_tz[CONST_CHAMP_TRANSITION_OFFSET]

        print("tz transition a %s" % transition_offset)

        # Ecraser l'information courante. Ceci supprime l'information de transition qui vient de prendre effet.
        await set_timezone_offset(transition_offset, timezone)
    except (KeyError, OSError, ValueError):
        pass


async def set_timezone_offset(offset, timezone=None, transition_time=None, transition_offset=None):
    print("Offset : %s" % offset)

    # Charger info, aucun write si information non changee
    try:
        with open(CONST_PATH_TZOFFSET, CONST_READ_BINARY) as fichier:
            tz_courant = load(fichier)
    except (OSError, ValueError):
        print('tzoffset.json absent/invalide')
        diff = True
        tz_courant = dict()
    else:
        await sleep(0)
        diff = offset != tz_courant.get(CONST_CHAMP_OFFSET)
        diff |= timezone and timezone != tz_courant.get(CONST_CHAMP_TIMEZONE)
        if transition_time and transition_offset:
            try:
                diff |= transition_time and transition_time != tz_courant.get(CONST_CHAMP_TRANSITION_TIME)
                diff |= transition_offset and transition_offset != tz_courant.get(CONST_CHAMP_TRANSITION_OFFSET)
            except TypeError:
                diff = True

    if diff:
        print("overwrite %s" % CONST_PATH_TZOFFSET)
        with open(CONST_PATH_TZOFFSET, CONST_WRITE_BINARY) as fichier:
            params = {
                CONST_CHAMP_OFFSET: offset,
                CONST_CHAMP_TIMEZONE: timezone or tz_courant.get(CONST_CHAMP_TIMEZONE),
                CONST_CHAMP_TRANSITION_TIME: transition_time or tz_courant.get(CONST_CHAMP_TRANSITION_TIME),
                CONST_CHAMP_TRANSITION_OFFSET: transition_offset or tz_courant.get(CONST_CHAMP_TRANSITION_OFFSET)
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
        with open(CONST_PATH_SOLAIRE, CONST_READ_BINARY) as fichier:
            solaire_courant = load(fichier)
    except OSError:
        # sauvegarder information directement
        with open(CONST_PATH_SOLAIRE, CONST_WRITE_BINARY) as fichier:
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
        with open(CONST_PATH_SOLAIRE, CONST_READ_BINARY) as fichier:
            return load(fichier)
    except OSError:
        return


def set_configuration_display(configuration: dict):
    # print('Maj configuration display')
    with open(CONST_PATH_FICHIER_DISPLAY, CONST_WRITE_BINARY) as fichier:
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
    with open(CONST_PATH_FICHIER_PROGRAMMES, CONST_WRITE_BINARY) as fichier:
        dump(configuration, fichier)
    

def sauvegarder_relais(fiche: dict):
    app_instance_pathname = dict()
    for instance_id, app_params in fiche[CONST_CHAMP_APPLICATIONSV2][CONST_CHAMP_SENSEURSPASSIFS_RELAI][CONST_CHAMP_INSTANCES].items():
        try:
            app_instance_pathname[instance_id] = app_params[CONST_CHAMP_PATHNAME]
            # print("instance_id %s pathname %s" % (instance_id, app_params[CONST_CHAMP_PATHNAME]))
        except KeyError:
            pass

    print("relais %d instances" % len(app_instance_pathname))

    url_relais = list()
    for instance_id, instance_params in fiche[CONST_CHAMP_INSTANCES].items():
        try:
            pathname = app_instance_pathname[instance_id]
        except KeyError:
            continue  # Pas de path

        try:
            port = instance_params[CONST_CHAMP_PORTS][CONST_CHAMP_HTTPS]
        except KeyError:
            port = 443

        try:
            for domaine in instance_params[CONST_CHAMP_DOMAINES]:
                url_relais.append(f'https://{domaine}:{port}{pathname}')
        except KeyError:
            pass

    if len(url_relais) > 0:
        sauvegarder_relais_liste(url_relais)

    return url_relais


def sauvegarder_relais_liste(url_relais: list):
    """
    Sauvegarde la liste de relais recu d'une fiche de MilleGrille.
    Supprime relais.new.json.
    """
    if len(url_relais) == 0:
        # Empecher le retrait de tous les relais, on doit en garder au moins 1.
        raise ValueError('liste vide')

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
    elif len(info_relais[CONST_CHAMP_RELAIS]) != len(url_relais):
        change = True
    else:
        for relai in url_relais:
            if relai not in info_relais[CONST_CHAMP_RELAIS]:
                change = True

    if change:
        print('Sauvegarder %s maj' % CONST_PATH_RELAIS)
        try:
            with open(CONST_PATH_RELAIS, CONST_WRITE_BINARY) as fichier:
                dump({CONST_CHAMP_RELAIS: url_relais}, fichier)
        except Exception as e:
            print('Erreur sauvegarde %s' % CONST_PATH_RELAIS)
            print_exception(e)
    else:
        print("Relais non changes")

    try:
        # Cleanup relais.new.json
        unlink(CONST_PATH_RELAIS_NEW)
        print("relais.new.json supprime")
    except OSError:
        pass  # Le fichier n'existe pas


def get_relais():
    """ Charge les listes de relais.json et relais.new.json. """
    relais = list()

    try:
        with open(CONST_PATH_RELAIS, CONST_READ_BINARY) as fichier:
            relais.extend(load(fichier)[CONST_CHAMP_RELAIS])
    except (OSError, KeyError):
        pass

    try:
        with open(CONST_PATH_RELAIS_NEW, CONST_READ_BINARY) as fichier:
            relais.extend(load(fichier)[CONST_CHAMP_RELAIS])
    except (OSError, KeyError):
        pass

    return relais


async def set_time():
    from ntptime import settime
    import time
    import urequests
    from millegrilles.webutils import parse_url

    # ntptime.host = 'maple.maceroc.com'
    try:
        settime()
        print("NTP Time : ", time.gmtime())
    except OSError as e:
        import sys
        print('NTP erreur')
        print_exception(e)
        await sleep(0)

        # Tenter acces via relais
        url_relais = get_relais()
        if url_relais:
            for relai in url_relais:
                print("parse relai %s" % relai)
                proto, host, port, pathname = parse_url(relai)
                # print("relai %s:%s" % (host, port))
                url_time = 'http://%s/%s' % (host, 'time.txt')
                reponse = urequests.get(url_time)
                await sleep(0)
                if reponse.status_code == 200:
                    time_reponse = reponse.text
                    # print("time reponse text : %s" % time_reponse)
                    await sleep(0)
                    time_reponse_int = int(time_reponse.split('.')[0])
                    print("time reponse : %s -> %s" % (time_reponse, time_reponse_int))
                    from machine import RTC
                    year, month, day, hour, minute, second, dow, doy = time.gmtime(time_reponse_int)
                    rtc = RTC()
                    rtc.datetime((year, month, day, dow, hour, minute, second, None))
                    return

        raise e
