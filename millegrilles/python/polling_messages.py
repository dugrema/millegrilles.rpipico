import uasyncio as asyncio

PATHNAME_POLL = const('/poll')
CONST_CHAMP_TIMEOUT = const('http_timeout')


class HttpErrorException(Exception):
    pass


async def __preparer_message(timeout_http, generer_etat):
    from mgmessages import signer_message

    # Genrer etat
    if generer_etat is not None:
        etat = await generer_etat()
    else:
        etat = {'lectures_senseurs': {}}
        
    # Ajouter timeout pour limite polling
    etat[CONST_CHAMP_TIMEOUT] = timeout_http

    # Signer message
    etat = await signer_message(etat, domaine='SenseursPassifs', action='etatAppareil')

    return etat


async def poll(url_relai: str, timeout_http=60, generer_etat=None):
    from urequests2 import post
    
    etat = await __preparer_message(timeout_http, generer_etat)

    # Poll
    url_poll = url_relai + PATHNAME_POLL
    return await post(url_poll, json=etat)


async def verifier_reponse(reponse):
    try:
        status = reponse.status_code

        if status != 200:
            raise HttpErrorException('poll err http:%d' % status)

        return await reponse.json()  # Note : close la reponse automatiquement
    finally:
        reponse.close()


async def polling_thread(url_relai: str, timeout_http=60, generer_etat=None):
    from mgmessages import verifier_message
    from handler_commandes import traiter_commande
    from sys import print_exception
    
    errnumber = 0
    while True:
        try:
            reponse = await verifier_reponse(await poll(url_relai, timeout_http, generer_etat))
            info_certificat = await verifier_message(reponse)
            
            if reponse.get('ok') is False:
                print("Err %s" % reponse.get('err'))
            else:
                await traiter_commande(reponse)
                errnumber = 0  # Reset erreurs
        except HttpErrorException as e:
            raise e  # Retour pour recharger fiche/changer relai
        except Exception as e:
            print("POLLING ERR")
            errnumber += 1
            if errnumber == 3:
                raise e  # On abandonne
            print_exception(e)
            await asyncio.sleep(10)
