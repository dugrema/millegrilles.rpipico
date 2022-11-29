import uasyncio as asyncio
from mgmessages import verifier_message
from handler_commandes import traiter_commande
import urequests2 as urequests

# url_poll = 'http://mg-dev1.maple.maceroc.com:4443/appareils/poll'
PATHNAME_POLL = '/senseurspassifs_relai/poll'


def get_url_relai():
    import json
    with open('conn.json') as fichier:
        config = json.load(fichier)
    return config['relai']


async def poll(timeout_http=60):
    from etat import generer_etat
    etat = await generer_etat(timeout_http=timeout_http)
    url_poll = get_url_relai() + PATHNAME_POLL
    return await urequests.post(url_poll, json=etat)


async def verifier_reponse(reponse):
    status = reponse.status_code

    if status != 200:
        reponse.close()
        raise Exception('poll err http:%d' % status)

    reponse = await reponse.json()  # Note : close la reponse automatiquement
    return reponse


async def polling_thread(timeout_http=60):
    while True:
        reponse = await verifier_reponse(await poll(timeout_http))
        info_certificat = await verifier_message(reponse)
        print("Source reponse %s (fp: %s)" % (info_certificat['roles'], info_certificat['fingerprint']))
        if reponse.get('ok') is False:
            print("Err %s" % reponse.get('err'))
        else:
            await traiter_commande(reponse)


async def __main():
    asyncio.create_task(polling_thread(10))
    await asyncio.sleep(2 * 3600)


if __name__ == '__main__':
    asyncio.run(__main())
