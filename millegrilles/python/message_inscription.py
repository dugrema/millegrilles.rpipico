import json
import time

from binascii import hexlify
from machine import unique_id
from os import rename, remove
from sys import print_exception
from uasyncio import sleep

import urequests2 as requests

from certificat import valider_certificats, charger_cle_publique, \
     get_expiration_certificat_local, generer_cle_secrete, \
     PATH_CERT, PATH_CLE_PRIVEE, PATHNAME_RENOUVELER
from mgmessages import signer_message, verifier_message


# Generer le nom d'appareil avec le machine unique_id du RPi PICO
NOM_APPAREIL = 'rpi-pico-' + hexlify(unique_id()).decode('utf-8')
print("Nom appareil : %s" % NOM_APPAREIL)

CONST_PATH_INSCRIPTION = '/inscrire'
CONST_CSR_BEGIN = const('-----BEGIN CERTIFICATE REQUEST-----')
CONST_CSR_END = const('-----END CERTIFICATE REQUEST-----')


async def generer_message_inscription(user_id: str):
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

    try:
        with open(PATH_CLE_PRIVEE + '.new', 'rb') as fichier:
            cle_privee = fichier.read()
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


async def post_inscription(url, message):
    print("post_inscription ", url)
    
    certificat_recu = False
    
    reponse = await requests.post(url, json=message)
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
    # Valider le certificat
    ts = time.time()
    print("Recevoir cert avec date : %s" % ts)
    info_certificat = await valider_certificats(certificat.copy(), ts)
    print("Certificat recu valide, info : %s" % info_certificat)
    await sleep(0.01)  # Yield
    
    # Comparer avec notre cle publique
    cle_publique_recue = info_certificat['public_key']
    cle_publique_locale = charger_cle_publique(PATH_CLE_PRIVEE + '.new')
    
    if cle_publique_recue != cle_publique_locale:
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


async def run_challenge(challenge, ui_lock=None):
    from ledblink import led_executer_sequence
    print("Run challenge %s" % challenge)
    await led_executer_sequence(challenge, 2, ui_lock=ui_lock)


async def run_inscription(url_relai: str, user_id: str, ui_lock):
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
        except OSError:
            raise
        except Exception as e:
            print("Erreur reception certificat")
            print_exception(e)

        await sleep(10)

    print("Certificat recu")


async def verifier_renouveler_certificat(url_relai: str):
    print("Verifier renouveler cert url %s" % url_relai)
    
    date_expiration, _ = get_expiration_certificat_local()
    # if time.time() > (date_expiration - CONST_RENOUVELLEMENT_DELAI):
    #    print("Cert renouvellement atteint")
    #    await renouveler_certificat(url_relai)
    
    requete = await signer_message({'csr': generer_csr()})
    requete = json.dumps(requete)
    reponse = await requests.post(
        url_relai + PATHNAME_RENOUVELER,
        data=requete,
        headers={'Content-Type': 'application/json'}
    )
    requete = None
    
    try:
        status = reponse.status_code
        print("Reponse renouveler certificat %s" % status)
    finally:
        reponse.close()
