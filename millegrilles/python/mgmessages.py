# Test PEM
import oryx_crypto
import json
import math
import time
from multiformats import multibase, multihash
from collections import OrderedDict

MARQUEUR_END_CERTIFICATE = b'-----END CERTIFICATE-----'
IDMG_VERSION_ACTIVE = 2
VERSION_SIGNATURE = 2
CONST_HACHAGE_FINGERPRINT = 'blake2s-256'

OID_EXCHANGES = bytearray([0x2a, 0x03, 0x04, 0x00])
OID_ROLES = bytearray([0x2a, 0x03, 0x04, 0x01])
OID_DOMAINES = bytearray([0x2a, 0x03, 0x04, 0x02])


def calculer_fingerprint(contenu_der):
    """ Calculer le fingerprint d'un certificat """
    fingerprint = oryx_crypto.blake2s(contenu_der)
    fingerprint = multihash.wrap(CONST_HACHAGE_FINGERPRINT, fingerprint)
    fingerprint = multibase.encode('base58btc', bytes(fingerprint))
    return fingerprint


def load_pem_certificat(pem_path):
    """ Charge un PEM de certificat et split la chaine. Retourne en format DER. """
    with open(pem_path, 'b') as fichier:
        pem = fichier.read()
    return split_pem(pem)


def split_pem(pem_contenu):
    """ Split une str de certificats PEM, transforme en DER """
    certs = []
    for pem in pem_contenu.split(MARQUEUR_END_CERTIFICATE):
        if pem != b'\n':
            pem = pem + MARQUEUR_END_CERTIFICATE
            pem = pem.strip()
            contenu_der = oryx_crypto.x509readpemcertificate(pem)
            certs.append(contenu_der)
    return certs


#def valider_ca():
#    contenu_der = load_pem('ca.pem')
#    current_time = time.time()
#    oryx_crypto.x509validercertificate(contenu_der[0], contenu_der[0], current_time)


def calcul_idmg(ca_der):
    import struct
    
    x509_info = oryx_crypto.x509certificatinfo(ca_der)
    
    fingerprint = oryx_crypto.blake2s(ca_der)
    fingerprint = multihash.wrap(CONST_HACHAGE_FINGERPRINT, fingerprint)

    date_expiration = oryx_crypto.x509EndDate(x509_info)
    date_expiration = float(date_expiration) / 1000.0
    date_expiration = math.ceil(date_expiration)
    date_expiration = int(date_expiration)
    
    IDMG_VERSION_PACK = '<BI'
    
    valeur_combinee = struct.pack(IDMG_VERSION_PACK, IDMG_VERSION_ACTIVE, date_expiration)
    valeur_combinee = valeur_combinee + fingerprint
    
    return multibase.encode('base58btc', bytes(valeur_combinee))


def signer_message(message, cle_privee):
    """ Genere l'en-tete et la signature d'un message """
    entete, signature = __signer_message(message, cle_privee)
    message['en-tete'] = entete
    message['_signature'] = signature
    return message    


def __signer_message(message, cle_privee):
    message = prep_message_1(message)
    hachage = hacher_message(message).decode('utf-8')
    entete = generer_entete(hachage)
    message['en-tete'] = entete
    
    # Re-trier le message
    message = prep_message_1(message)
    
    # Signer
    signature = __signer_message_2(message, cle_privee).decode('utf-8')

    return entete, signature


def __signer_message_2(message, cle_privee):
    cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)

    hachage = oryx_crypto.blake2b(message_stringify(message))
    
    signature = bytes([VERSION_SIGNATURE]) + oryx_crypto.ed25519sign(cle_privee, cle_publique, hachage)
    signature = multibase.encode('base64', signature)
    
    return signature


def generer_entete(hachage,
                   domaine: str = None,
                   version: int = 1,
                   action: str = None,
                   partition: str = None):
    entete = OrderedDict([])

    if action is not None:
        entete['action'] = action
    if domaine is not None:
        entete['domaine'] = domaine
    entete['estampille'] = time.time()
    entete['fingerprint'] = 'DUMMY_FINGERPRINT'
    entete['hachage_contenu'] = hachage
    entete['idmg'] = 'DUMMY_IDMG'
    if partition is not None:
        entete['partition'] = partition
    entete['uuid_transaction'] = 'DUMMY_UUID'

    return entete


def hacher_message(message):
    hachage = oryx_crypto.blake2s(message_stringify(message))
    fingerprint = multihash.wrap(CONST_HACHAGE_FINGERPRINT, hachage)
    return multibase.encode('base64', bytes(fingerprint))


def prep_message_1(message, conserver_entete=True):
    message_prep = OrderedDict([])

    # Re-inserer toutes les key/values en ordre
    # Filtrer/transformer les valeurs au besoin
    for (key, value) in sorted(message.items(), key = lambda ele: ele[0]):
        if key.startswith('_'):
            continue
        
        if key == 'en-tete' and conserver_entete is False:
            continue
        
        if isinstance(value, float):
            # Retirer le .0 (convertir en int) si applicable
            if math.floor(value) == value:
                value = int(value)
        
        elif isinstance(value, dict):
            # Appel recursif
            value = prep_message_1(value)
            
        message_prep[key] = value
    
    return message_prep


def message_stringify(message):
    #message_prep_hachage = prep_message_1(message)
    #print("Message prep hacahge avant json\n%s" % message_prep_hachage)
    return json.dumps(message, separators=(',', ':')).encode('utf-8')


def verifier_message(message: dict):
    # Valider le certificat - raise Exception si erreur
    info_certificat = valider_certificats(message['_certificat'])
    del message['_certificat']

    # Verifier la signature du message
    signature = message['_signature']
    del message['_signature']

    # Trier tous les champs
    message = prep_message_1(message)

    verifier_signature(message, signature, info_certificat['public_key'])
    
    return info_certificat


def valider_certificats(pem_certs: list, date_validation=time.time(), is_der=False):
    """ Valide la chaine de certificats, incluant le dernier avec le CA.
        @return Information du certificat leaf
        @raises Exception Si la chaine est invalide. """
    cert = pem_certs.pop(0)
    if is_der is False:
        cert = oryx_crypto.x509readpemcertificate(cert)
    
    # Conserver l'information du certificat leaf
    x509_info = oryx_crypto.x509certificatinfo(cert)
    fingerprint = calculer_fingerprint(cert)
    
    # Parcourir la chaine. Valider le dernier certificat avec le CA
    while len(pem_certs) > 0:
        parent = pem_certs.pop(0)
        if is_der is False:
            parent = oryx_crypto.x509readpemcertificate(parent)
        oryx_crypto.x509validercertificate(cert, parent, date_validation)
        cert = parent  # Poursuivre la chaine
    else:
        parent = load_pem_certificat('ca.pem')[0]
        oryx_crypto.x509validercertificate(cert, parent, date_validation)
        
    enveloppe = {
        'fingerprint': fingerprint,
        'public_key': oryx_crypto.x509PublicKey(x509_info),
        'expiration': oryx_crypto.x509EndDate(x509_info),
        'exchanges': oryx_crypto.x509Extension(x509_info, OID_EXCHANGES).split(','),
        'roles': oryx_crypto.x509Extension(x509_info, OID_ROLES).split(','),
        'domaines': oryx_crypto.x509Extension(x509_info, OID_DOMAINES).split(','),
    }
    
    return enveloppe


def verifier_signature(message, signature, cle_publique):
    """ Verifie la signature d'un message. Lance une exception en cas de signature invalide. """
    signature = multibase.decode(signature)

    version_signature = signature[0]
    if version_signature != VERSION_SIGNATURE:
        raise Exception("Signature non supportee")
    
    hachage = oryx_crypto.blake2b(message_stringify(message))
    oryx_crypto.ed25519verify(cle_publique, signature[1:], hachage)

