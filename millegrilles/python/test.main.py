import binascii
import oryx_crypto
import time
import machine
from gc import collect
from micropython import mem_info

from millegrilles.certificat import split_pem, calculer_fingerprint, valider_certificats, \
     entretien_certificat, charger_cle_privee, charger_cle_publique, generer_cle_secrete, rnd_bytes
from millegrilles.mgmessages import BufferMessage, signer_message_2023_5, verifier_signature_2023_5, \
     hacher_message_2023_5, verifier_message, formatter_message


def afficher_info():
    print('---')
    print("Heure %s" % str(time.gmtime()))
    print("CPU freq %d" % machine.freq())
    print("Memoire")
    mem_info()
    print('---\n')
    

def charger_userid_local():
    print("User id du certificat local : %s" % get_userid_local())


# DEV Tests
def test_charger_cles():
    cle_privee_generee = binascii.hexlify(generer_cle_secrete())
    print("Cle privee generee %s" % cle_privee_generee)
    cle_publique = binascii.hexlify(charger_cle_publique())
    print("Cle publique %s" % cle_publique)
    cle_privee = binascii.hexlify(charger_cle_privee())
    print("Cle privee %s" % cle_privee)
    

def certificat_fingerprint():
    print('\n********************\ncertificat_fingerprint()\n')
    # Convertir le certificat PEM en DER
    certificat = split_pem(PEM_CERTICIAT, format_str=False).pop()
    fingerprint = calculer_fingerprint(certificat)
    print(fingerprint)


async def test_valider_certificat():
    print('\n********************\ntest_valider_certificat()\n')
    certificat = split_pem(PEM_CERTICIAT, format_str=False)

    ticks_debut = time.ticks_ms()
    enveloppe_certificat = await valider_certificats(certificat, is_der=True, fingerprint=None)
    print("test_valider_certificat Parse certificat %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    
    fingerprint = enveloppe_certificat['fingerprint']
    print('Fingerprint %s' % fingerprint)
    certificat = split_pem(PEM_CERTICIAT, format_str=False)
    ticks_debut = time.ticks_ms()
    enveloppe_certificat = await valider_certificats(certificat, is_der=True, fingerprint=fingerprint)
    print("test_valider_certificat Certificat cache certificat %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    print('Enveloppe cache? %s' % enveloppe_certificat)
    
    await entretien_certificat()
    fingerprint = enveloppe_certificat['fingerprint']
    print('Fingerprint %s' % fingerprint)
    certificat = split_pem(PEM_CERTICIAT, format_str=False)
    ticks_debut = time.ticks_ms()
    enveloppe_certificat = await valider_certificats(certificat, is_der=True, fingerprint=fingerprint)
    print("test_valider_certificat Certificat cache certificat %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    print('Enveloppe cache? %s' % enveloppe_certificat)


async def signer_message():
    print('\n********************\nsigner_message()\n')
    id_message = '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff'
    signature = await signer_message_2023_5(id_message)
    print("Signature message")
    print(signature)
    
    cle_publique = 'b92eafcce1d99315556ba552190a03f3541155c546b3ca858bcac5c9f71fa6ab'
    
    try:
        verifier_signature_2023_5(id_message, signature, cle_publique)
        print("Resultat verification signature : OK")
    except:
        print("Resultat verification signature : ECHEC")
    

async def hacher_message():
    print('\n********************\nhacher_message()\n')
    buffer = BufferMessage()
    pubkey = 'b92eafcce1d99315556ba552190a03f3541155c546b3ca858bcac5c9f71fa6ab'
    estampille = time.time()
    kind = 1
    contenu = 'Juste du contenu DUMMY sans autre structure, devrait etre JSON'
    routage = {'domaine': 'DummyDomaine', 'action': 'testHacher'}
    
    message_dict = {
        'pubkey': pubkey,
        'estampille': estampille,
        'kind': kind,
        'contenu': contenu,
        'routage': routage,
    }
    
    id_message = await hacher_message_2023_5(message_dict)
    print("id message (hachage) : %s" % id_message)
    id_message_buffer = await hacher_message_2023_5(message_dict, buffer=buffer)
    print("id message avec buffer (hachage) : %s" % id_message_buffer)
    

async def test_verifier_message():
    print('\n********************\ntest_verifier_message()\n')
    buffer = BufferMessage()
    await verifier_message(MESSAGE_TEST, buffer, err_ca_ok=True)


async def test_formatter_message():
    print('\n********************\ntest_formatter_message()\n')
    buffer = BufferMessage()
    message_contenu = {'texte': 'Un texte a emettre', 'nombre': 1234}
    kind = 1
    
    message_signe = await formatter_message(message_contenu, kind, domaine='DomaineDummy', action='testAction', buffer=buffer, ajouter_certificat=False)
    print("Message signe\n%s" % message_signe)


async def generer_cles_exchange():
    buf_privee_a = b"01234567890123456789012345678901"
    print("generer_cles_exchange cle privee a %s" % binascii.hexlify(buf_privee_a).decode('utf-8'))
    buf_public_a = oryx_crypto.x25519generatepubkey(buf_privee_a)
    print("generer_cles_exchange cle publique A %s" % binascii.hexlify(buf_public_a).decode('utf-8'))

    # buf_privee_b = b"01234567890123456789012345678902"
    buf_privee_b = rnd_bytes(32)
    print("generer_cles_exchange cle privee b %s" % binascii.hexlify(buf_privee_b).decode('utf-8'))
    buf_public_b = oryx_crypto.x25519generatepubkey(buf_privee_b)
    print("generer_cles_exchange cle publique B %s" % binascii.hexlify(buf_public_b).decode('utf-8'))
    
    secret_a = oryx_crypto.x25519computesharedsecret(buf_privee_a, buf_public_b)
    secret_b = oryx_crypto.x25519computesharedsecret(buf_privee_b, buf_public_a)
    print("generer_cles_exchange output secret A %s" % binascii.hexlify(secret_a).decode('utf-8'))
    print("generer_cles_exchange output secret B %s" % binascii.hexlify(secret_b).decode('utf-8'))

def chiffrage_chacha20poly1305():
    buf_secret = b"01234567890123456789012345678901"  # 32 bytes
    buf_nonce = b"0123456789ad"  # 12 bytes
    buf_message = b"ABCD12345678EFGHABRAdada"
    debut = time.ticks_us()
    tag = oryx_crypto.cipherchacha20poly1305encrypt(buf_secret, buf_nonce, buf_message)
    tag_b64 = binascii.b2a_base64(tag).decode('utf-8')[:-1]
    print("-- Tag b64: '%s' --" % tag_b64)
    print("duree chiffrage : %s" % (time.ticks_us()-debut))
    print("resultat chiffrage ciphertext : %s" % binascii.hexlify(buf_message).decode('utf-8'))
    print("resultat chiffrage tag : %s" % binascii.hexlify(tag).decode('utf-8'))
    
    buf_nonce_tag = buf_nonce + tag
    debut = time.ticks_us()
    oryx_crypto.cipherchacha20poly1305decrypt(buf_secret, buf_nonce_tag, buf_message)
    print("duree dechiffrage : %s" % (time.ticks_us()-debut))
    print("resultat dechiffrage plaintext : %s" % buf_message.decode('utf-8'))
    

async def run_tests():
    # print("Delai demarrage - 3 secs")
    afficher_info()
    # time.sleep(3)
    print("Running tests")
    
    #await hacher_message()
    #test_charger_cles()
    #certificat_fingerprint()
    #await signer_message()
    #await test_formatter_message()
    # await generer_cles_exchange()
    # await test_valider_certificat()
    # await test_verifier_message()
    # charger_userid_local()
    chiffrage_chacha20poly1305()


IDMG = "zeYncRqEqZ6eTEmUZ8whJFuHG796eSvCTWE4M432izXrp22bAtwGm7Jf"


PEM_CERTICIAT = """
-----BEGIN CERTIFICATE-----
MIIClDCCAkagAwIBAgIUOdCKB8xpReL4Kook9gMlVayADqwwBQYDK2VwMHIxLTAr
BgNVBAMTJGY4MmEzMWU5LWE1YjEtNDFiYi04MmE3LWUzMmE0ODIwNmFhNzFBMD8G
A1UEChM4emVZbmNScUVxWjZlVEVtVVo4d2hKRnVIRzc5NmVTdkNUV0U0TTQzMml6
WHJwMjJiQXR3R203SmYwHhcNMjMwNDI0MDAyODM4WhcNMjMwNTI1MDAyODU4WjCB
gTEtMCsGA1UEAwwkZjgyYTMxZTktYTViMS00MWJiLTgyYTctZTMyYTQ4MjA2YWE3
MQ0wCwYDVQQLDARjb3JlMUEwPwYDVQQKDDh6ZVluY1JxRXFaNmVURW1VWjh3aEpG
dUhHNzk2ZVN2Q1RXRTRNNDMyaXpYcnAyMmJBdHdHbTdKZjAqMAUGAytlcAMhAKA0
i2lqQidVvGR0c5BTAumhcCJcoaANFBprXtA5TU45o4HdMIHaMCsGBCoDBAAEIzQu
c2VjdXJlLDMucHJvdGVnZSwyLnByaXZlLDEucHVibGljMAwGBCoDBAEEBGNvcmUw
TAYEKgMEAgREQ29yZUJhY2t1cCxDb3JlQ2F0YWxvZ3VlcyxDb3JlTWFpdHJlRGVz
Q29tcHRlcyxDb3JlUGtpLENvcmVUb3BvbG9naWUwDwYDVR0RBAgwBoIEY29yZTAf
BgNVHSMEGDAWgBT9WXyy8Enb2WXCZo2pCW0k8xZdIjAdBgNVHQ4EFgQUdTdbp3gk
Lcqetbwg810k66oh/LAwBQYDK2VwA0EAtRZvjiHORV2qD4GGNWilWPX/ZRmOuJku
9PKAtbDvW4YRVEZcjwPfUyPn+IIWeip4kYxiaCfWiAiZngTJ8X+RBg==
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIIBozCCAVWgAwIBAgIKB3IHZERSFHVxWTAFBgMrZXAwFjEUMBIGA1UEAxMLTWls
bGVHcmlsbGUwHhcNMjMwNDI0MDAyODQ0WhcNMjQxMTAyMDAyODQ0WjByMS0wKwYD
VQQDEyRmODJhMzFlOS1hNWIxLTQxYmItODJhNy1lMzJhNDgyMDZhYTcxQTA/BgNV
BAoTOHplWW5jUnFFcVo2ZVRFbVVaOHdoSkZ1SEc3OTZlU3ZDVFdFNE00MzJpelhy
cDIyYkF0d0dtN0pmMCowBQYDK2VwAyEAPRJtFycOSNwfJKgcZHXIs5jox77M9N9Y
O53LQqVo2v2jYzBhMBIGA1UdEwEB/wQIMAYBAf8CAQAwCwYDVR0PBAQDAgEGMB0G
A1UdDgQWBBT9WXyy8Enb2WXCZo2pCW0k8xZdIjAfBgNVHSMEGDAWgBTTiP/MFw4D
DwXqQ/J2LLYPRUkkETAFBgMrZXADQQBVsyArA+J2GFEDnKgK9rLCS9SRX2G5VpO5
YJfezh6rSzo51qv04rlKQSLfw9owrLbdoqyjNqetjgE9A/z7bVEH
-----END CERTIFICATE-----
"""

MESSAGE_TEST = {
  "id": "83b1511d7da1fb49e20ac557b8ce38dcb1d5a429a8c8e0c7bcc216e41bf7e192",
  "pubkey": "f8a8429cb16a4f03103c711c00ceb47bc7a95c0f114b9ef5ad02b31cb4e9fbb2",
  "estampille": 1682175772,
  "kind": 5,
  "contenu": "{}",
  "routage": {
    "action": "certMaitreDesCles",
    "domaine": "MaitreDesCles"
  },
  "sig": "e4646b66e1b84aefdd2c007dc93ff7a29f3444dba97165e792f0deccc6d9f8d7fd9a0074f03c9090e2ea3fef68aef5d2a96622b1147f0503ab69d063deb2c60c",
  "certificat": [
    "-----BEGIN CERTIFICATE-----\nMIICaTCCAhugAwIBAgIUSU88Q3RYk7G3VPAS1FdOSvLsdDYwBQYDK2VwMHIxLTAr\nBgNVBAMTJDU5ODc4MGI5LTc3MjctNDkyMi04ZjFlLTRhN2QxN2MwNDIyNDFBMD8G\nA1UEChM4emVZbmNScUVxWjZlVEVtVVo4d2hKRnVIRzc5NmVTdkNUV0U0TTQzMml6\nWHJwMjJiQXR3R203SmYwHhcNMjMwNDIxMjMzNjAwWhcNMjMwNTIyMjMzNjIwWjCB\nijEtMCsGA1UEAwwkNTk4NzgwYjktNzcyNy00OTIyLThmMWUtNGE3ZDE3YzA0MjI0\nMRYwFAYDVQQLDA1tYWl0cmVkZXNjbGVzMUEwPwYDVQQKDDh6ZVluY1JxRXFaNmVU\nRW1VWjh3aEpGdUhHNzk2ZVN2Q1RXRTRNNDMyaXpYcnAyMmJBdHdHbTdKZjAqMAUG\nAytlcAMhAPioQpyxak8DEDxxHADOtHvHqVwPEUue9a0Csxy06fuyo4GpMIGmMCsG\nBCoDBAAEIzQuc2VjdXJlLDMucHJvdGVnZSwyLnByaXZlLDEucHVibGljMCAGBCoD\nBAEEGG1haXRyZWRlc2NsZXMsbWFpdHJlY2xlczAVBgQqAwQCBA1NYWl0cmVEZXND\nbGVzMB8GA1UdIwQYMBaAFLuz2/F6bNrZSapzF30qxKjaAdt6MB0GA1UdDgQWBBTk\nknNitOPKXFBQFhd1ttxz1zCLWzAFBgMrZXADQQBb3cpH7Yj9KhB9hpJ2vzu6nida\njw6V26yFMWwFOVgMWSDfyGIXeb9oRFUdccUmKpASMJvBItG6De8RrKkpU5oH\n-----END CERTIFICATE-----\n",
    "-----BEGIN CERTIFICATE-----\nMIIBozCCAVWgAwIBAgIKEmmCcheYQlgilzAFBgMrZXAwFjEUMBIGA1UEAxMLTWls\nbGVHcmlsbGUwHhcNMjMwNDIwMTYwMjA1WhcNMjQxMDI5MTYwMjA1WjByMS0wKwYD\nVQQDEyQ1OTg3ODBiOS03NzI3LTQ5MjItOGYxZS00YTdkMTdjMDQyMjQxQTA/BgNV\nBAoTOHplWW5jUnFFcVo2ZVRFbVVaOHdoSkZ1SEc3OTZlU3ZDVFdFNE00MzJpelhy\ncDIyYkF0d0dtN0pmMCowBQYDK2VwAyEA5MsRSn1ijF04Te/Gicl7VODKquu0fNDW\nr9BUvoHV6YCjYzBhMBIGA1UdEwEB/wQIMAYBAf8CAQAwCwYDVR0PBAQDAgEGMB0G\nA1UdDgQWBBS7s9vxemza2Umqcxd9KsSo2gHbejAfBgNVHSMEGDAWgBTTiP/MFw4D\nDwXqQ/J2LLYPRUkkETAFBgMrZXADQQB8EW5M9T3BKcydydmDhPcIVf0ijtMGg6IV\nNFnxvRADj2vlVuvlwiMfU9674wjaAjIGxgMRqdPi9uPe0YqtZpAK\n-----END CERTIFICATE-----\n"
  ]
}

from uasyncio import run

run(run_tests())




