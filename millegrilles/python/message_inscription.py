import binascii
import machine
import mgmessages
import urequests2 as urequests
import uasyncio as asyncio
import ledblink
import time

# Generer le nom d'appareil avec le machine unique_id du RPi PICO
NOM_APPAREIL = 'rpi-pico-' + binascii.hexlify(machine.unique_id()).decode('utf-8')
print("Nom appareil : %s" % NOM_APPAREIL)

CONST_PATH_INSCRIPTION = '/senseurspassifs_relai/inscrire'


async def generer_message_inscription():
    
    # Generer message d'inscription
    message_inscription = {
        "uuid_appareil": NOM_APPAREIL,
        "csr": generer_csr(),
    }

    return await mgmessages.signer_message(message_inscription, action='inscrire')


def generer_csr():
    from oryx_crypto import x509CsrNew
    with open('certs/secret.key', 'rb') as fichier:
        cle_privee = fichier.read()
    resultat = x509CsrNew(cle_privee, NOM_APPAREIL.encode('utf-8'))
    return format_pem(binascii.b2a_base64(resultat, newline=False).decode('utf-8'))


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
    certificat_recu = False
    
    reponse = await urequests.post(url, json=message)
    status = reponse.status_code
    print("status code : %s" % status)

    if status not in [200, 202]:
        reponse.close()
        raise Exception('err http:%d' % status)
    
    # Valider la reponse
    reponse = await reponse.json()
    info_certificat = await mgmessages.verifier_message(reponse)
    print("reponse valide, info certificat:\n%s" % info_certificat)
    roles = info_certificat.get('roles') or list()
    exchanges = info_certificat.get('exchanges') or list()
    if status == 200:
        # Valider le message
        if 'senseurspassifs' not in roles or '4.secure' not in exchanges is None:
            raise Exception('role certificat invalide : %s, exchanges %s' % (roles, exchanges))
        
        if reponse['ok'] is not True:
            raise Exception("Reponse ok:false")

        # Extraire Certificat
        try:
            certificat = reponse['certificat']
        except KeyError:
            pass  # On n'a pas recu le certificat
        else:
            await recevoir_certificat(certificat)
            certificat_recu = True
        
        # Extraire challenge/confirmation
        try:
            challenge = reponse['challenge']
        except KeyError:
            pass
        else:
            await run_challenge(challenge)
        
    elif status == 202:
        if 'senseurspassifs_relai' not in roles or exchanges is None:
            raise Exception('role serveur invalide : %s' % roles)
    elif reponse.get('ok') is False:
        print("Erreur inscription : %s" % reponse.get('err'))
        
    return certificat_recu


async def recevoir_certificat(certificat):
    # Valider le certificat
    ts = time.time()
    print("Recevoir cert avec date : %s" % ts)
    info_certificat = await mgmessages.valider_certificats(certificat.copy(), ts)
    print("Certificat recu valide, info : %s" % info_certificat)
    await asyncio.sleep(0.01)  # Yield
    
    # Verifier CN
    #if info_certificat['cn'] != NOM_APPAREIL:
    #    raise Exception("Mauvais CN")
    
    # Comparer avec notre cle publique
    cle_publique_recue = info_certificat['public_key']
    cle_publique_locale = charger_cle_publique()
    
    if cle_publique_recue != cle_publique_locale:
        raise Exception("Mismatch cert/cle publique")
    
    # Sauvegarder le nouveau certificat
    with open('certs/cert.pem', 'w') as fichier:
        for cert in certificat:
            fichier.write(cert)


async def run_challenge(challenge):
    print("Run challenge %s" % challenge)
    await ledblink.led_executer_sequence(challenge, 2)


async def run_inscription(url_relai: str):
    import sys
    url_inscription = url_relai + CONST_PATH_INSCRIPTION
    message_signe = await generer_message_inscription()
    print("Message signe\n%s" % message_signe)
    certificat_recu = False
    while certificat_recu is False:
        try:
            certificat_recu = await post_inscription(url_inscription, message_signe)
        except Exception as e:
            print("Erreur reception certificat")
            sys.print_exception(e)
            await asyncio.sleep(10)

    print("Certificat recu")


if __name__ == '__main__':
    asyncio.run(run_inscription())
