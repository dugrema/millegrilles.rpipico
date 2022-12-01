# Test PEM
import oryx_crypto
import json
import os
import math
import time
import ubinascii
import uasyncio

from struct import pack
from random import getrandbits

from multiformats import multibase, multihash
from collections import OrderedDict

MARQUEUR_END_CERTIFICATE = b'-----END CERTIFICATE-----'
IDMG_VERSION_ACTIVE = 2
VERSION_SIGNATURE = 2
CONST_HACHAGE_FINGERPRINT = 'blake2s-256'

OID_EXCHANGES = bytearray([0x2a, 0x03, 0x04, 0x00])
OID_ROLES = bytearray([0x2a, 0x03, 0x04, 0x01])
OID_DOMAINES = bytearray([0x2a, 0x03, 0x04, 0x02])

PATH_CERTS = 'certs'
PATH_CA_CERT = 'certs/ca.der'
PATH_CLE_PRIVEE = 'certs/secret.key'
PATH_CERT = 'certs/cert.pem'


def calculer_fingerprint(contenu_der):
    """ Calculer le fingerprint d'un certificat """
    fingerprint = oryx_crypto.blake2s(contenu_der)
    fingerprint = multihash.wrap(CONST_HACHAGE_FINGERPRINT, fingerprint)
    fingerprint = multibase.encode('base58btc', bytes(fingerprint))
    return fingerprint


def load_pem_certificat(pem_path, format_str=False):
    """ Charge un PEM de certificat et split la chaine. Retourne en format DER. """
    with open(pem_path, 'b') as fichier:
        pem = fichier.read()
    return split_pem(pem, format_str)


def split_pem(pem_contenu, format_str=False):
    """ Split une str de certificats PEM, transforme en DER """
    if isinstance(pem_contenu, str):
        pem_contenu = pem_contenu.encode('utf-8')
    certs = []
    for pem in pem_contenu.split(MARQUEUR_END_CERTIFICATE):
        if pem not in [b'', b'\n']:
            pem = pem + MARQUEUR_END_CERTIFICATE
            pem = pem.strip()
            if format_str is False:
                contenu = oryx_crypto.x509readpemcertificate(pem)
            else:
                contenu = pem.decode('utf-8')
            certs.append(contenu)
    return certs


def calculer_idmg(ca_der):
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


async def signer_message(message, cle_privee=None, **kwargs):
    """ Genere l'en-tete et la signature d'un message """
    entete, signature = await __signer_message(message, cle_privee, **kwargs)
    message['en-tete'] = entete
    message['_signature'] = signature
    if entete.get('fingerprint_certificat') is not None:
        message['_certificat'] = split_pem(get_certificat_local(), format_str=True)
    return message    


def get_certificat_local():
    try:
        with open(PATH_CERT, 'r') as fichier:
            return fichier.read()
        return load_pem_certificat(PATH_CERT)
    except OSError:
        return None


async def __signer_message(message, cle_privee=None, **kwargs):
    message = prep_message_1(message)
    hachage = hacher_message(message).decode('utf-8')

    try:
        cert_local = load_pem_certificat(PATH_CERT)[0]
        fingerprint = calculer_fingerprint(cert_local)
    except OSError:
        fingerprint = None
    
    entete = await generer_entete(hachage, fingerprint=fingerprint, **kwargs)
    message['en-tete'] = entete
    
    # Re-trier le message
    message = prep_message_1(message)
    
    # Signer
    uasyncio.sleep(0.01)
    signature = __signer_message_2(message, cle_privee).decode('utf-8')
    # signature = __signer_message_2(message, cle_privee)

    return entete, signature


def __signer_message_2(message, cle_privee=None):
    if cle_privee is None:
        # Charger la cle locale
        with open(PATH_CLE_PRIVEE, 'rb') as fichier:
            cle_privee = fichier.read()
    cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)

    message_str = message_stringify(message)
    hachage = oryx_crypto.blake2b(message_str)
    
    signature = bytes([VERSION_SIGNATURE]) + oryx_crypto.ed25519sign(cle_privee, cle_publique, hachage)
    signature = multibase.encode('base64', signature)
    
    return signature


async def generer_entete(hachage,
                         domaine: str = None,
                         version: int = 1,
                         action: str = None,
                         partition: str = None,
                         fingerprint: str = None):
    entete = OrderedDict([])

    with open(PATH_CA_CERT, 'rb') as fichier:
        ca_der = fichier.read()
    uasyncio.sleep(0.01)
    idmg = calculer_idmg(ca_der).decode('utf-8')
    
    cle_publique = None
    if fingerprint is None:
        with open(PATH_CLE_PRIVEE, 'rb') as fichier:
            cle_privee = fichier.read()
        uasyncio.sleep(0.01)
        cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)
        uasyncio.sleep(0.01)
        cle_privee = None
        cle_publique = multibase.encode('base64', cle_publique)

    if action is not None:
        entete['action'] = action
    if cle_publique is not None:
        entete['cle_publique'] = cle_publique
    if domaine is not None:
        entete['domaine'] = domaine
    entete['estampille'] = time.time()
    if fingerprint is not None:
        entete['fingerprint_certificat'] = fingerprint
    entete['hachage_contenu'] = hachage
    entete['idmg'] = idmg
    if partition is not None:
        entete['partition'] = partition
    entete['uuid_transaction'] = str(uuid4())

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
        
        message_prep[key] = __traiter_value(value)
    
    return message_prep


def __traiter_value(value):
    if isinstance(value, float):
        # Retirer le .0 (convertir en int) si applicable
        if math.floor(value) == value:
            value = int(value)
    
    elif isinstance(value, dict):
        # Appel recursif
        value = prep_message_1(value)
    
    elif isinstance(value, list):
        for i, liste_value in enumerate(value):
            value[i] = __traiter_value(liste_value)
    
    return value


def message_stringify(message):
    #message_prep_hachage = prep_message_1(message)
    #print("Message prep hachage avant json\n%s" % message_prep_hachage)
    return json.dumps(message, separators=(',', ':')).encode('utf-8')


async def verifier_message(message: dict):
    # Valider le certificat - raise Exception si erreur
    info_certificat = await valider_certificats(message['_certificat'])
    del message['_certificat']

    # Verifier la signature du message
    signature = message['_signature']
    del message['_signature']

    # Trier tous les champs
    message = prep_message_1(message)

    uasyncio.sleep(0.01)
    verifier_signature(message, signature, info_certificat['public_key'])
    
    return info_certificat


async def valider_certificats(pem_certs: list, date_validation=time.time(), is_der=False):
    """ Valide la chaine de certificats, incluant le dernier avec le CA.
        @return Information du certificat leaf
        @raises Exception Si la chaine est invalide. """
    print("valider_certificats avec time %s" % date_validation)

    cert = pem_certs.pop(0)
    if is_der is False:
        cert = oryx_crypto.x509readpemcertificate(cert)
    
    # Conserver l'information du certificat leaf
    x509_info = oryx_crypto.x509certificatinfo(cert)
    fingerprint = calculer_fingerprint(cert)
    uasyncio.sleep(0.01)  # Yield

    # Parcourir la chaine. Valider le dernier certificat avec le CA
    while len(pem_certs) > 0:
        parent = pem_certs.pop(0)
        if is_der is False:
            parent = oryx_crypto.x509readpemcertificate(parent)
        uasyncio.sleep(0.01)  # Yield
        oryx_crypto.x509validercertificate(cert, parent, date_validation)
        cert = parent  # Poursuivre la chaine
    else:
        with open(PATH_CA_CERT, 'rb') as fichier:
            parent = fichier.read()
        uasyncio.sleep(0.01)  # Yield
        oryx_crypto.x509validercertificate(cert, parent, date_validation)
        
    exchanges = oryx_crypto.x509Extension(x509_info, OID_EXCHANGES)
    if exchanges is not None:
        exchanges = exchanges.split(',')
    roles = oryx_crypto.x509Extension(x509_info, OID_ROLES)
    if roles is not None:
        roles = roles.split(',')
    domaines = oryx_crypto.x509Extension(x509_info, OID_DOMAINES)
    if domaines is not None:
        domaines = domaines.split(',')
        
    enveloppe = {
        'fingerprint': fingerprint,
        'public_key': oryx_crypto.x509PublicKey(x509_info),
        'expiration': oryx_crypto.x509EndDate(x509_info),
        'exchanges': exchanges,
        'roles': roles,
        'domaines': domaines,
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


def sauvegarder_ca(ca_pem, idmg=None):
    
    try:
        os.mkdir(PATH_CERTS)
    except OSError as e:
        if e.errno == 17:
            pass
        else:
            raise e
    
    if isinstance(ca_pem, str):
        ca_pem = ca_pem.encode('utf-8')
    elif not isinstance(ca_pem, bytes):
        raise TypeError("ca_pem")
    
    # Convertir en DER
    ca_der = oryx_crypto.x509readpemcertificate(ca_pem)
    
    if idmg is not None:
        # Valider le idmg
        if calculer_idmg(ca_der) != idmg.encode('utf-8'):
            raise Exception("Mismatch IDMG")
    
    # Valider (self-signed) - raise Exception si invalide
    oryx_crypto.x509validercertificate(ca_der, ca_der, time.time())
    
    with open(PATH_CA_CERT, 'wb') as fichier:
        fichier.write(ca_der)


def generer_cle_secrete():
    cle_privee = rnd_bytes(32)
    with open(PATH_CLE_PRIVEE, 'wb') as fichier:
        fichier.write(cle_privee)

    # Cleanup, retirer certs/cert.pem si present
    try:
        os.remove('certs/cert.pem')
    except OSError:
        pass

def rnd_bytes(nb_bytes):
    bytes_courant = nb_bytes
    rnd_val = bytes()
    while bytes_courant > 0:
        bytes_courant -= 4
        rnd_bits = getrandbits(32)  # 4 bytes
        rnd_val += bytes(pack('L', rnd_bits))
    
    return rnd_val[:nb_bytes]


# From : https://github.com/pfalcon/pycopy-lib
class UUID:
    def __init__(self, bytes):
        if len(bytes) != 16:
            raise ValueError('bytes arg must be 16 bytes long')
        self._bytes = bytes

    @property
    def hex(self):
        return ubinascii.hexlify(self._bytes).decode()

    def __str__(self):
        h = self.hex
        return '-'.join((h[0:8], h[8:12], h[12:16], h[16:20], h[20:32]))

    def __repr__(self):
        return "<UUID: %s>" % str(self)


def uuid4():
    """Generates a random UUID compliant to RFC 4122 pg.14"""
    random = bytearray(rnd_bytes(16))
    random[6] = (random[6] & 0x0F) | 0x40
    random[8] = (random[8] & 0x3F) | 0x80
    return UUID(bytes=random)

