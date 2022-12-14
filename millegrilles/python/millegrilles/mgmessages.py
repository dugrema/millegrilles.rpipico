# Test PEM
import json
import os
import math
import time
import uasyncio as asyncio
import oryx_crypto

from io import BytesIO

from . import certificat
from .certificat import valider_certificats

from multiformats import multibase, multihash
from collections import OrderedDict


VERSION_SIGNATURE = 2


async def signer_message(message, cle_privee=None, **kwargs):
    """ Genere l'en-tete et la signature d'un message """
    entete, signature = await __signer_message(message, cle_privee, **kwargs)
    message['en-tete'] = entete
    message['_signature'] = signature
    if entete.get('fingerprint_certificat') is not None:
        message['_certificat'] = certificat.split_pem(certificat.get_certificat_local(), format_str=True)
    return message    


async def __signer_message(message, cle_privee=None, **kwargs):
    message = prep_message_1(message)
    hachage = hacher_message(message).decode('utf-8')

    try:
        cert_local = certificat.load_pem_certificat(certificat.PATH_CERT)[0]
        fingerprint = certificat.calculer_fingerprint(cert_local)
    except OSError:
        fingerprint = None
    
    entete = await generer_entete(hachage, fingerprint=fingerprint, **kwargs)
    message['en-tete'] = entete
    
    # Re-trier le message
    message = prep_message_1(message)
    
    # Signer
    await asyncio.sleep_ms(10)
    signature = __signer_message_2(message, cle_privee).decode('utf-8')
    # signature = __signer_message_2(message, cle_privee)

    return entete, signature


def __signer_message_2(message, cle_privee=None):
    if cle_privee is None:
        # Charger la cle locale
        try:
            with open(certificat.PATH_CLE_PRIVEE, 'rb') as fichier:
                cle_privee = fichier.read()
        except OSError:
            print("Cle prive absente, utiliser .new")
            with open(certificat.PATH_CLE_PRIVEE + '.new', 'rb') as fichier:
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

    with open(certificat.PATH_CA_CERT, 'rb') as fichier:
        ca_der = fichier.read()
    await asyncio.sleep_ms(10)
    idmg = certificat.calculer_idmg(ca_der).decode('utf-8')
    
    cle_publique = None
    if fingerprint is None:
        try:
            with open(certificat.PATH_CLE_PRIVEE, 'rb') as fichier:
                cle_privee = fichier.read()
        except OSError:
            with open(certificat.PATH_CLE_PRIVEE + '.new', 'rb') as fichier:
                cle_privee = fichier.read()
                
        await asyncio.sleep_ms(10)
        cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)
        await asyncio.sleep_ms(10)
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
    entete['version'] = 1

    return entete


def hacher_message(message):
    from oryx_crypto import blake2s
    from multiformats.multihash import wrap
    from multiformats.multibase import encode
    from millegrilles.certificat import CONST_HACHAGE_FINGERPRINT
    
    hachage = blake2s(message_stringify(message))
    fingerprint = wrap(CONST_HACHAGE_FINGERPRINT, hachage)
    return encode('base64', bytes(fingerprint))


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

    await asyncio.sleep_ms(1)
    verifier_signature(message, signature, info_certificat['public_key'])
    
    return info_certificat


def verifier_signature(message, signature, cle_publique):
    from multiformats.multibase import decode
    from oryx_crypto import blake2b, ed25519verify
    
    """ Verifie la signature d'un message. Lance une exception en cas de signature invalide. """
    signature = decode(signature)

    version_signature = signature[0]
    if version_signature != VERSION_SIGNATURE:
        raise Exception("Signature non supportee")
    
    hachage = blake2b(message_stringify(message))
    ed25519verify(cle_publique, signature[1:], hachage)


# From : https://github.com/pfalcon/pycopy-lib
class UUID:
    def __init__(self, bytes):
        if len(bytes) != 16:
            raise ValueError('bytes arg must be 16 bytes long')
        self._bytes = bytes

    @property
    def hex(self):
        from ubinascii import hexlify
        return hexlify(self._bytes).decode()

    def __str__(self):
        h = self.hex
        return '-'.join((h[0:8], h[8:12], h[12:16], h[16:20], h[20:32]))

    def __repr__(self):
        return "<UUID: %s>" % str(self)


def uuid4():
    """Generates a random UUID compliant to RFC 4122 pg.14"""
    from millegrilles.certificat import rnd_bytes
    
    random = bytearray(rnd_bytes(16))
    random[6] = (random[6] & 0x0F) | 0x40
    random[8] = (random[8] & 0x3F) | 0x80
    return UUID(bytes=random)


# Buffer pour recevoir l'etat
class BufferMessage:

    def __init__(self, bufsize = 8*1024):
        self.__buffer = bytearray(bufsize)
        self.__len_courant = 0

    def get_data(self):
        return memoryview(self.__buffer)[:self.__len_courant]

    def set_text(self, data):
        self.set_bytes(data.encode('utf-8'))

    def set_bytes(self, data):
        if len(data) > len(self.__buffer):
            raise ValueError('overflow')
        self.__len_courant = len(data)
        self.__buffer[:self.__len_courant] = data

    def set_len(self, len_data):
        if len_data > len(self.__buffer):
            raise ValueError('overflow')
        self.__len_courant = len_data

    def clear(self):
        self.__len_courant = 0
        self.__buffer.clear()

    @property
    def buffer(self):
        return self.__buffer

    def __iter__(self):
        for i in range(0, self.__len_courant):
            yield self.__buffer[i]

    def __len__(self):
        return self.__len_courant

