from machine import unique_id
from binascii import hexlify


# Generer le nom d'appareil avec le machine unique_id du RPi PICO
NOM_APPAREIL = 'rpi-pico-' + hexlify(unique_id()).decode('utf-8')
print("Nom appareil : %s" % NOM_APPAREIL)

CONST_PATH_INSCRIPTION = '/inscrire'


async def generer_message_inscription(user_id: str):
    from mgmessages import signer_message
    
    # Generer message d'inscription
    message_inscription = {
        "uuid_appareil": NOM_APPAREIL,
        "user_id": user_id,
        "csr": generer_csr(),
    }

    return await signer_message(message_inscription, action='inscrire')


def generer_csr():
    from ubinascii import b2a_base64
    from oryx_crypto import x509CsrNew

    with open('certs/secret.key', 'rb') as fichier:
        cle_privee = fichier.read()
    resultat = x509CsrNew(cle_privee, NOM_APPAREIL.encode('utf-8'))
    return format_pem(b2a_base64(resultat, newline=False).decode('utf-8'))


def charger_cle_publique():
    from oryx_crypto import ed25519generatepubkey
    with open('certs/secret.key', 'rb') as fichier:
        cle_privee = fichier.read()
    return ed25519generatepubkey(cle_privee)


def format_pem(value):
    output = '-----BEGIN CERTIFICATE REQUEST-----'
    ligne = value[:64]
    value = value[64:]
    while len(ligne) > 0:
        output += '\n%s' % ligne
        ligne = value[:64]
        value = value[64:]
    output += '\n-----END CERTIFICATE REQUEST-----'
    return output


async def post_inscription(url, message):
    from urequests2 import post
    print("post_inscription ", url)
    
    certificat_recu = False
    
    reponse = await post(url, json=message)
    try:
        status_code = reponse.status_code
        print("status code : %s" % status_code)

        if status_code not in [200, 202]:
            raise Exception('err http:%d' % status_code)
        
        # Valider la reponse
        return status_code, await reponse.json()
    finally:
        reponse.close()


async def valider_reponse(status_code, reponse):
    from mgmessages import verifier_message
    
    info_certificat = await verifier_message(reponse)
    print("reponse valide, info certificat:\n%s" % info_certificat)
    roles = info_certificat.get('roles') or list()
    exchanges = info_certificat.get('exchanges') or list()
    
    if status_code == 200:
        # Valider le message
        if 'senseurspassifs' not in roles or '4.secure' not in exchanges is None:
            raise Exception('role certificat invalide : %s, exchanges %s' % (roles, exchanges))
        
        if reponse['ok'] is not True:
            raise Exception("Reponse ok:false")

        return True
        
    elif status_code == 202:
        if 'senseurspassifs_relai' not in roles or exchanges is None:
            raise Exception('role serveur invalide : %s' % roles)
    elif reponse.get('ok') is False:
        print("Erreur inscription : %s" % reponse.get('err'))
        
    return False


async def recevoir_certificat(certificat):
    from uasyncio import sleep
    from time import time as get_time
    from certificat import valider_certificats, PATH_CERT

    # Valider le certificat
    ts = get_time()
    print("Recevoir cert avec date : %s" % ts)
    info_certificat = await valider_certificats(certificat.copy(), ts)
    print("Certificat recu valide, info : %s" % info_certificat)
    await sleep(0.01)  # Yield
    
    # Comparer avec notre cle publique
    cle_publique_recue = info_certificat['public_key']
    cle_publique_locale = charger_cle_publique()
    
    if cle_publique_recue != cle_publique_locale:
        raise Exception("Mismatch cert/cle publique")
    
    # Sauvegarder le nouveau certificat
    with open(PATH_CERT, 'w') as fichier:
        for cert in certificat:
            fichier.write(cert)


async def run_challenge(challenge, ui_lock=None):
    from ledblink import led_executer_sequence
    print("Run challenge %s" % challenge)
    await led_executer_sequence(challenge, 2, ui_lock=ui_lock)


async def run_inscription(url_relai: str, user_id: str, ui_lock):
    from uasyncio import sleep
    from sys import print_exception

    url_inscription = url_relai + CONST_PATH_INSCRIPTION
    certificat_recu = False
    while certificat_recu is False:
        try:
            # Faire une demande d'inscription
            status_code, reponse_dict = await post_inscription(
                url_inscription, await generer_message_inscription(user_id))
            
            if await valider_reponse(status_code, reponse_dict) is True:
                # Extraire le certificat si fourni
                try:
                    certificat = reponse_dict['certificat']
                except KeyError:
                    pass  # On n'a pas recu le certificat
                else:
                    await recevoir_certificat(certificat)
                    certificat_recu = True
                
                # Extraire challenge/confirmation et executer si present
                try:
                    challenge = reponse_dict['challenge']
                except KeyError:
                    pass
                else:
                    await run_challenge(challenge, ui_lock)
                
        except Exception as e:
            print("Erreur reception certificat")
            print_exception(e)

        await sleep(10)

    print("Certificat recu")

