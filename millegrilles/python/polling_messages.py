import json
import time
import uasyncio as asyncio

import urequests2 as requests

from gc import collect
from sys import print_exception

from mgmessages import signer_message, verifier_message
from handler_commandes import traiter_commande

PATHNAME_POLL = const('/poll')
PATHNAME_REQUETE = const('/requete')
CONST_CHAMP_TIMEOUT = const('http_timeout')

CONST_DOMAINE_SENSEURSPASSIFS = const('SenseursPassifs')
CONST_REQUETE_DISPLAY = const('getAppareilDisplayConfiguration')

CONST_DUREE_THREAD_POLLING = const(3 * 60 * 60)

class HttpErrorException(Exception):
    pass


async def __preparer_message(timeout_http, generer_etat):
    # Genrer etat
    if generer_etat is not None:
        etat = await generer_etat()
    else:
        etat = {'lectures_senseurs': {}}
        
    # Ajouter timeout pour limite polling
    etat[CONST_CHAMP_TIMEOUT] = timeout_http

    # Signer message
    etat = await signer_message(etat, domaine=CONST_DOMAINE_SENSEURSPASSIFS, action='etatAppareil')
    etat = json.dumps(etat)

    return etat


async def poll(url_relai: str, timeout_http=60, generer_etat=None):
    etat = await __preparer_message(timeout_http, generer_etat)

    # Cleanup memoire
    await asyncio.sleep_ms(100)
    collect()

    # Poll
    url_poll = url_relai + PATHNAME_POLL
    return await requests.post(
        url_poll, data=etat, headers={'Content-Type': 'application/json'})


async def requete_configuration_displays(url_relai: str, set_configuration):
    requete = await signer_message(dict(), domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_DISPLAY)
    requete = json.dumps(requete)

    # Cleanup memoire
    await asyncio.sleep_ms(100)
    collect()
    
    url_requete = url_relai + PATHNAME_REQUETE
    print('Requete displays sur %s' % url_requete)
    try:
        reponse = await verifier_reponse(await requests.post(
            url_requete, data=requete, headers={'Content-Type': 'application/json'}))
        requete = None
    except OSError as e:
        raise e  # Faire remonter erreur
    except Exception as e:
        print('Erreur requete configuration')
        print_exception(e)
        return

    try:
        if reponse['ok'] == True:
            info_certificat = await verifier_message(reponse)
            if CONST_DOMAINE_SENSEURSPASSIFS in info_certificat['domaines']:
                try:
                    set_configuration(reponse['display_configuration']['configuration']['displays'])
                except KeyError:
                    print('Configuration displays sans information - pass')
    except Exception as e:
        print("Erreur validation reponse displays")
        print_exception(e)


async def verifier_reponse(reponse):
    try:
        status = reponse.status_code

        if status != 200:
            raise HttpErrorException('poll err http:%d' % status)

        return await reponse.json()  # Note : close la reponse automatiquement
    finally:
        reponse.close()


async def verifier_signature(reponse):
    return await verifier_message(reponse)


async def _traiter_commande(appareil, reponse):
    return await traiter_commande(appareil, reponse)


async def polling_thread(appareil, url_relai: str, timeout_http=60, generer_etat=None):
    # Cleanup memoire
    #await asyncio.sleep(4)
    #collect()
    #await asyncio.sleep(1)
    
    await requete_configuration_displays(url_relai, appareil.set_configuration_display)

    # Cleanup memoire
    #await asyncio.sleep(4)
    #collect()
    #await asyncio.sleep(1)

    # Faire expirer la thread pour reloader la fiche/url, entretien certificat
    expiration_thread = time.time() + CONST_DUREE_THREAD_POLLING
    
    errnumber = 0
    while expiration_thread > time.time():
        try:
            reponse = await verifier_reponse(await poll(url_relai, timeout_http, generer_etat))
            info_certificat = await verifier_signature(reponse)
            
            if reponse.get('ok') is False:
                print("Polling complete, msg %s" % reponse.get('err'))
            else:
                await _traiter_commande(appareil, reponse)
            reponse = None
            errnumber = 0  # Reset erreurs
        except OSError as e:
            print("POLLING OSError %d" % e.errno)
            if e.errno == 12 and errnumber == 0:
                # Erreur memoire, on tente a nouveau
                errnumber += 1
                await asyncio.sleep(2)
            else:
                print_exception(e)
                raise e
        except HttpErrorException as e:
            raise e  # Retour pour recharger fiche/changer relai
        except Exception as e:
            print("POLLING ERR")
            errnumber += 1
            if errnumber == 3:
                raise e  # On abandonne
            print_exception(e)
            await asyncio.sleep(10)
