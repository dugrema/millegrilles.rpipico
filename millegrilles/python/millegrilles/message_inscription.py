import json
import time
import urequests

from binascii import hexlify
from machine import unique_id
from os import rename, remove
from sys import print_exception
from uasyncio import sleep, sleep_ms
from gc import collect
from json import loads

from millegrilles import urequests2 as requests
from millegrilles.certificat import valider_certificats, \
     generer_cle_secrete, charger_cle_privee, charger_cle_publique, \
     get_expiration_certificat_local, PATH_CERT, PATH_CLE_PRIVEE
from millegrilles.config import get_user_id, get_idmg, sauvegarder_relais, get_relais
from millegrilles.mgthreads import dump_spawn

from millegrilles.webutils import parse_url


# Generer le nom d'appareil avec le machine unique_id du RPi PICO
NOM_APPAREIL = 'rpi-pico-' + hexlify(unique_id()).decode('utf-8')
print("Nom appareil : %s" % NOM_APPAREIL)

CONST_RENOUVELLEMENT_DELAI = const(6 * 24 * 60 * 60)  # jours pour renouvellement

CONST_PATH_INSCRIPTION = '/inscrire'
CONST_CSR_BEGIN = const('-----BEGIN CERTIFICATE REQUEST-----')
CONST_CSR_END = const('-----END CERTIFICATE REQUEST-----')


async def generer_message_inscription(cryptographie, watchdog, buffer, action='inscrire', domaine=None):
    # Generer message d'inscription
    message_inscription = {
        "uuid_appareil": NOM_APPAREIL,
        "user_id": get_user_id(),
        "csr": generer_csr(),
    }

    #message_inscription = await signer_message(
    #    message_inscription, action=action, domaine=domaine, buffer=buffer)
    message_inscription = await cryptographie.formatter_message(
        message_inscription, kind=1, action=action, domaine=domaine,
        buffer=buffer, ajouter_certificat=False)

    buffer.clear()
    watchdog.feed()
    # json.dump(message_inscription, buffer)
    await dump_spawn(watchdog, message_inscription, buffer)
    # message_inscription = None
    
    # return message_inscription
    return buffer


def generer_csr():
    from ubinascii import b2a_base64
    from oryx_crypto import x509CsrNew

    try:
        # with open(PATH_CLE_PRIVEE + '.new', 'rb') as fichier:
        #    cle_privee = fichier.read()
        cle_privee = charger_cle_privee(PATH_CLE_PRIVEE + '.new')
    except OSError:
        cle_privee = generer_cle_secrete()
    
    resultat = x509CsrNew(cle_privee, NOM_APPAREIL.encode('utf-8'))
    return format_pem_csr(b2a_base64(resultat, newline=False).decode('utf-8'))


def format_pem_csr(value):
    output = ''
    ligne = value[:64]
    value = value[64:]
    while len(ligne) > 0:
        output += '\n%s' % ligne
        ligne = value[:64]
        value = value[64:]
    return CONST_CSR_BEGIN + output + '\n' + CONST_CSR_END


async def post_inscription(url, buffer):
    print("post_inscription ", url)
    
    certificat_recu = False
    
    reponse = await requests.post(
        url,
        data=buffer.get_data(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        status_code = reponse.status_code
        print("status code : %s" % status_code)

        if status_code not in [200, 202]:
            raise Exception('err http:%d' % status_code)
        
        # Valider la reponse
        await reponse.read_text_into(buffer)
        return status_code, buffer
    finally:
        reponse.close()


async def valider_reponse(cryptographie, watchdog, status_code: int, reponse: dict, buffer=None):
    
    if status_code not in[200, 202]:
        print("Erreur inscription : %s" % reponse.get('err'))
    else:    
        info_certificat = await cryptographie.verifier_message(reponse, buffer=buffer)
        print("reponse valide, info certificat:\n%s" % info_certificat)
        roles = info_certificat.get('roles') or list()
        exchanges = info_certificat.get('exchanges') or list()

        contenu = json.loads(reponse['contenu'])

        if status_code == 200:
            # Valider le message
            if 'senseurspassifs' not in roles or '4.secure' not in exchanges is None:
                raise Exception('role certificat invalide : %s, exchanges %s' % (roles, exchanges))
            
            if contenu.get('ok') is not True:
                raise Exception("Reponse ok:false")

            return True
            
        elif status_code == 202:
            if 'senseurspassifs_relai' not in roles or exchanges is None:
                raise Exception('role serveur invalide : %s' % roles)
        
        elif contenu.get('ok') is False:
            print("Erreur inscription : %s" % contenu.get('err'))
        
    return False


async def recevoir_certificat(watchdog, certificat):
    # Valider le certificat
    ts = time.time()
    print("Recevoir cert avec date : %s" % ts)
    info_certificat = await valider_certificats(watchdog, certificat.copy(), ts)
    print("Certificat recu valide, info : %s" % info_certificat)
    await sleep_ms(10)  # Yield
    
    # Comparer avec notre cle publique
    cle_publique_recue = info_certificat['public_key']
    cle_publique_locale = charger_cle_publique(PATH_CLE_PRIVEE + '.new')
    
    if cle_publique_recue != cle_publique_locale:
        print('cle recue/cle locale\n%s\n%s' % (hexlify(cle_publique_recue), hexlify(cle_publique_locale)))
        raise Exception("Mismatch cert/cle publique")
    
    # Sauvegarder le nouveau certificat
    with open(PATH_CERT + '.new', 'w') as fichier:
        for cert in certificat:
            fichier.write(cert)
            
    # Faire rotation de l'ancien cert/cle
    try:
        remove(PATH_CERT)
    except OSError:
        pass
    try:
        remove(PATH_CLE_PRIVEE)
    except OSError:
        pass
    
    rename(PATH_CLE_PRIVEE + '.new', PATH_CLE_PRIVEE)
    rename(PATH_CERT + '.new', PATH_CERT)
    print("Nouveau certificat installe")
    
    return True


async def run_challenge(appareil, challenge, ui_lock=None):
    from millegrilles.ledblink import led_executer_sequence
    print("Run challenge %s" % challenge)
    
    try:
        if appareil.display_actif:
            challenge_str = [str(code) for code in challenge]
            display = [
                'Activation',
                'Code: %s' % ','.join(challenge_str)
            ]
            appareil.set_display_override(display, duree=30)
        else:
            await led_executer_sequence(challenge, 2, ui_lock=ui_lock)
    except Exception as e:
        print("Erreur override display")
        print_exception(e)


async def run_inscription(appareil, url_relai: str, ui_lock, buffer):
    url_inscription = url_relai + CONST_PATH_INSCRIPTION
    certificat_recu = False
    # watchdog = appareil.watchdog
    async with appareil.watchdog as watchdog:
        try:
            # Faire une demande d'inscription
            await generer_message_inscription(appareil.cryptographie, watchdog, buffer)

            # Garbage collect
            # await sleep_ms(1)
            await watchdog.yield_duration(1)
            collect()
            watchdog.feed()
            # await sleep_ms(20)
            await watchdog.yield_duration(20)

            watchdog.feed()
            status_code, buffer_reponse = await post_inscription(url_inscription, buffer)
            watchdog.feed()

            # Garbage collect
            # await sleep_ms(1)  # Yield
            await watchdog.yield_duration(1)
            collect()
            await watchdog.yield_duration(20)
            # await sleep_ms(20)  # Yield

            reponse_dict = json.loads(buffer_reponse.get_data())

            if await valider_reponse(appareil.cryptographie, watchdog, status_code, reponse_dict, buffer=buffer) is True:
                # Extraire le certificat si fourni dans contenu
                buffer.set_text(reponse_dict['contenu'])
                reponse_dict = None
                await watchdog.yield_duration(1)
                collect()
                await watchdog.yield_duration(1)
                # await sleep_ms(1)  # Yield
                reponse_dict = json.loads(buffer.get_data())

                try:
                    certificat = reponse_dict['certificat']
                except KeyError:
                    pass  # On n'a pas recu le certificat
                else:
                    certificat_recu = await recevoir_certificat(watchdog, certificat)

                # Extraire challenge/confirmation et executer si present
                try:
                    challenge = reponse_dict['challenge']
                except KeyError:
                    pass
                else:
                    try:
                        await run_challenge(appareil, challenge, ui_lock)
                    except Exception:
                        pass  # OK

        except OSError:
            raise
        except Exception as e:
            print("Erreur reception certificat")
            print_exception(e)
        
    return certificat_recu

async def verifier_renouveler_certificat_ws(cryptographie, watchdog, websocket, buffer):
    date_expiration, _ = get_expiration_certificat_local()
    print("Date expiration certificat local : %s" % date_expiration)
    if time.time() > (date_expiration - CONST_RENOUVELLEMENT_DELAI):
       print("Cert renouvellement atteint")
    else:
        print("Cert valide jusqu'a %s" % date_expiration)
        return False
    
    await generer_message_inscription(cryptographie, watchdog, buffer, action='signerAppareil', domaine='SenseursPassifs')

    # Garbage collect
    # sleep_ms(1)  # Yield
    await watchdog.yield_duration(1)
    collect()
    # sleep_ms(1)  # Yield
    await watchdog.yield_duration(1)

    websocket.send(buffer.get_data())

    # Reponse recue via websocket_messages
    return True


async def recuperer_ca(cryptographie, watchdog, buffer=None):
    from millegrilles.certificat import sauvegarder_ca
    
    print("Init millegrille")
    idmg = get_idmg()
    # Charger et valider la fiche - (no_validation est pour le certificat seulement)
    fiche, certificat = await charger_fiche(cryptographie, watchdog, no_validation=True, buffer=buffer)
    # del fiche['_millegrille']
    
    if fiche['idmg'] != idmg:
        raise Exception('IDMG mismatch')
    
    print("IDMG OK : %s" % idmg)
    
    # Sauvegarder le certificat CA
    sauvegarder_ca(fiche['ca'], idmg)
    
    # Valider le certificat avec le CA et conserver relais
    info_cert = await valider_certificats(watchdog, certificat)
    print("Verifier roles cert fiche : %s" % info_cert.get('roles'))
    if 'core' not in info_cert['roles']:
       raise Exception("Fiche signee par mauvais role")

    # Sauvegarder les relais dans relais.json
    sauvegarder_relais(fiche)


async def charger_fiche(cryptographie, watchdog, no_validation=False, buffer=None):
    liste_urls = set()
    relais = get_relais()
    if len(relais) == 0:
        raise Exception('relais non diponibles')
    for relai in relais:
        proto, host, port, pathname = parse_url(relai)
        proto = 'http:'
        liste_urls.add(proto + '//' + host)

    recu_ok = False
    for url_instance in liste_urls:
        fiche_url = url_instance + '/fiche.json'
        print("charger_fiche url %s" % fiche_url)

        # Downloader la fiche
        # print("Recuperer fiche a %s" % fiche_url)
        # await watchdog.yield_duration(1)
        # await sleep_ms(1)  # Yield
        try:
            # reponse = await requests.get(fiche_url, lock=ui_lock)
            async with watchdog:
                reponse = urequests.get(fiche_url)
            watchdog.feed()
        except OSError as e:
            if e.errno in (103, 104, -2):
                # ECONNABORTED ou connexion refusee/serveur introuvable, essayer prochain relai
                print("errno %s connexion %s" % (e.errno, fiche_url))
                continue
            else:
                raise e

        try:
            # await sleep_ms(1)  # Yield
            await watchdog.yield_duration(1)
            if reponse.status_code != 200:
                # raise Exception("fiche http status:%d" % reponse.status_code)
                print("Erreur fiche %s status = %s" % (fiche_url, reponse.status_code))
                continue

            # await reponse.read_text_into(buffer)
            buffer.set_bytes(reponse.content)
            watchdog.feed()
            reponse = None
            recu_ok = True
            break  # Ok
        except AttributeError:
            # Verifier si on a eu un redirect sur https (generateur)
            try:
                reponse.__next__()
                print('Erreur fiche https')
            except Exception:
                print('Erreur chargement fiche (1)')
                continue
        except Exception as e:
            print('Erreur chargement fiche (2)')
            print_exception(e)
            continue
        finally:
            # print("charger_fiche fermer reponse")
            # reponse.close()
            # reponse = None

            # Cleanup memoire
            # await watchdog.yield_duration(1)
            collect()
            # watchdog.feed()
            # await sleep_ms(1)  # Yield
            await watchdog.yield_duration(1)

    if recu_ok is True:
        # collect()
        # await sleep_ms(1)  # Yield
        try:
            watchdog.feed()
            message_fiche = loads(buffer.get_data())
        except Exception as e:
            print('Erreur parse fiche')
            with open('fiche.err', 'wb') as fiche:
                fiche.write(buffer.get_data())
            raise e
        finally:
            watchdog.feed()

        print("Fiche recue id %s" % message_fiche['id'])
        certificat = message_fiche.get('certificat')
        if no_validation is False:
            await watchdog.yield_duration(1)
            info_cert = await cryptographie.verifier_message(message_fiche, buffer=buffer)
            if 'core' not in info_cert['roles']:
                raise Exception('Fiche a un mauvais certificat')
            certificat = None  # Certificat valide, cleanup
        
        # Transferer contenu dans le buffer pour faire parsing du json
        try:
            print("Parse contenu fiche %s" % message_fiche['id'])
            buffer.set_text(message_fiche['contenu'])
            message_fiche = None
            await sleep_ms(1)  # Yield
            collect()
            await sleep_ms(1)  # Yield
            return loads(buffer.get_data()), certificat
        except Exception as e:
            print("Erreur parsing fiche %s", e)

    return None, None


async def generer_message_timeinfo(cryptographie, watchdog, timezone_str: str):
    # Generer message d'inscription
    message_inscription = {
        "timezone": timezone_str,
    }
    message_inscription = await cryptographie.formatter_message(message_inscription, kind=1, action='getTimezoneInfo', ajouter_certificat=False)
    
    # Garbage collect
    await watchdog.yield_duration(200)
    collect()
    await watchdog.yield_duration(1)

    return message_inscription
