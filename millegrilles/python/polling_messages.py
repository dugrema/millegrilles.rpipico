import uasyncio as asyncio
from mgmessages import verifier_message
from handler_commandes import traiter_commande
import urequests2 as urequests

PATHNAME_POLL = const('/poll')
CONST_CHAMP_TIMEOUT = const('http_timeout')


async def poll(url_relai: str, timeout_http=60, generer_etat=None):
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

    # Poll
    url_poll = url_relai + PATHNAME_POLL
    return await urequests.post(url_poll, json=etat)


async def verifier_reponse(reponse):
    status = reponse.status_code

    if status != 200:
        reponse.close()
        raise Exception('poll err http:%d' % status)

    reponse = await reponse.json()  # Note : close la reponse automatiquement
    return reponse


async def polling_thread(url_relai: str, timeout_http=60, generer_etat=None):
    while True:
        reponse = await verifier_reponse(await poll(url_relai, timeout_http, generer_etat))
        info_certificat = await verifier_message(reponse)
        # print("Source reponse %s (fp: %s)" % (info_certificat['roles'], info_certificat['fingerprint']))
        if reponse.get('ok') is False:
            print("Err %s" % reponse.get('err'))
        else:
            await traiter_commande(reponse)
