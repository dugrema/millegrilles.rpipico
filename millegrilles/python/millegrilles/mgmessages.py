# Test PEM
import binascii
import json
import math
import time
import uasyncio as asyncio
import oryx_crypto

from gc import collect
from io import IOBase

from . import certificat
from .certificat import valider_certificats
# -- DEV --
#from millegrilles import certificat
#from millegrilles.certificat import valider_certificats
# -- DEV --

from multiformats import multibase, multihash
from collections import OrderedDict


VERSION_SIGNATURE = 2


# async def signer_message(message, cle_privee=None, buffer=None, task_runner=None, **kwargs):
#     """ Genere l'en-tete et la signature d'un message """
#     entete, signature = await __signer_message(message, cle_privee, buffer, task_runner, **kwargs)
#     message['en-tete'] = entete
#     message['_signature'] = signature
#     if entete.get('fingerprint_certificat') is not None:
#         message['_certificat'] = certificat.split_pem(certificat.get_certificat_local(), format_str=True)
#     return message    


# async def __signer_message(message, cle_privee=None, buffer=None, task_runner=None, **kwargs):
#     message = prep_message_1(message)
#     hachage = hacher_message(message, buffer).decode('utf-8')
#     await asyncio.sleep_ms(10)
# 
#     try:
#         cert_local = certificat.load_pem_certificat(certificat.PATH_CERT)[0]
#         fingerprint = certificat.calculer_fingerprint(cert_local)
#     except OSError:
#         fingerprint = None
#     await asyncio.sleep_ms(10)
# 
#     entete = await generer_entete(hachage, fingerprint=fingerprint, **kwargs)
#     await asyncio.sleep_ms(10)
#     message['en-tete'] = entete
#     
#     # Re-trier le message
#     message = prep_message_1(message)
#     
#     # Signer
#     await asyncio.sleep_ms(10)
#     signature = (await __signer_message_2(message, cle_privee, buffer, task_runner)).decode('utf-8')
#     # signature = __signer_message_2(message, cle_privee)
# 
#     return entete, signature


# async def __signer_message_2(message, cle_privee=None, buffer=None, task_runner=None):
#     if cle_privee is None:
#         # Charger la cle locale
#         try:
#             with open(certificat.PATH_CLE_PRIVEE, 'rb') as fichier:
#                 cle_privee = fichier.read()
#         except OSError:
#             print("Cle prive absente, utiliser .new")
#             with open(certificat.PATH_CLE_PRIVEE + '.new', 'rb') as fichier:
#                 cle_privee = fichier.read()
# 
#     ticks_debut = time.ticks_ms()
#     cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)
#     print("__signer_message_2 ed25519generatepubkey duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
#     await asyncio.sleep_ms(10)
# 
#     message_str = message_stringify(message, buffer=buffer)
#     await asyncio.sleep_ms(10)
#     ticks_debut = time.ticks_ms()
#     hachage = oryx_crypto.blake2b(message_str)
#     print("__signer_message_2 blake2b duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
#     await asyncio.sleep_ms(10)
# 
#     ticks_debut = time.ticks_ms()
#     signature = bytes([VERSION_SIGNATURE]) + oryx_crypto.ed25519sign(cle_privee, cle_publique, hachage)
#     print("__signer_message_2 ed25519sign duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
# 
#     await asyncio.sleep_ms(10)
#     signature = multibase.encode('base64', signature)
#     
#     return signature


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


# def hacher_message(message, buffer=None):
#     from oryx_crypto import blake2s
#     from multiformats.multihash import wrap
#     from multiformats.multibase import encode
#     from millegrilles.certificat import CONST_HACHAGE_FINGERPRINT
#     
#     ticks_debut = time.ticks_ms()
#     hachage = blake2s(message_stringify(message, buffer=buffer))
#     print("hacher_message stringify+blake2s duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
#     fingerprint = wrap(CONST_HACHAGE_FINGERPRINT, hachage)
#     return encode('base64', bytes(fingerprint))


def prep_message_1(message, conserver_entete=True):
    message_prep = OrderedDict([])

    # Re-inserer toutes les key/values en ordre
    # Filtrer/transformer les valeurs au besoin
    for (key, value) in sorted(message.items(), key=lambda ele: ele[0]):
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


def message_stringify(message, buffer=None):
    if buffer is None:
        return json.dumps(message, separators=(',', ':')).encode('utf-8')
    else:
        buffer.clear()
        json.dump(message, buffer, separators=(',', ':'))
        return buffer.get_data()


async def verifier_message(message: dict, buffer=None):
    # Valider le certificat - raise Exception si erreur
    pubkey = message['pubkey']

    ticks_debut = time.ticks_ms()
    info_certificat = await valider_certificats(message['certificat'])  #, fingerprint=message['pubkey'])
    print("verifier_message verifier certificat duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    del message['certificat']

    # Verifier la signature du message
    signature = message['sig']
    id_message = message['id']
    # Raise une exception si la signature est invalide
    verifier_signature_2023_5(id_message, signature, pubkey)

    # Hacher le message, comparer id
    id_calcule = hacher_message_2023_5(message, buffer=buffer)
    if id_calcule != id_message:
        print('Mismatch, id_calcule : %s, id_message : %s' % (id_calcule, id_message))
        raise Exception('Mismatch id message')

    return info_certificat


# async def __verifier_signature(message, signature, cle_publique, buffer=None, task_runner=None):
#     from multiformats.multibase import decode
#     from oryx_crypto import blake2b, ed25519verify
#     
#     """ Verifie la signature d'un message. Lance une exception en cas de signature invalide. """
#     signature = decode(signature)
# 
#     version_signature = signature[0]
#     if version_signature != VERSION_SIGNATURE:
#         raise Exception("Signature non supportee")
# 
#     await asyncio.sleep_ms(10)
#     ticks_debut = time.ticks_ms()
#     data = message_stringify(message, buffer=buffer)
#     print("__verifier_signature stringify duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
#     await asyncio.sleep_ms(10)
#     ticks_debut = time.ticks_ms()
#     hachage = blake2b(data)
#     print("__verifier_signature stringify blake2b %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
#     await asyncio.sleep_ms(10)
#     ticks_debut = time.ticks_ms()
#     #if task_runner is not None:
#     #    await task_runner.run_task(ed25519verify, cle_publique, signature[1:], hachage)
#     #else:
#     ed25519verify(cle_publique, signature[1:], hachage)
#     print("__verifier_signature ed25519verify duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))


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
class BufferMessage(IOBase):

    def __init__(self, bufsize=8*1024):
        super().__init__()
        self.__buffer = bytearray(bufsize)
        self.__len_courant = 0

    def get_data(self):
        return memoryview(self.__buffer)[:self.__len_courant]

    def set_text(self, data):
        try:
            if len(data) > len(self.__buffer):
                raise ValueError('overflow')
        except TypeError:
            pass  # Pas de len sur data

        pos = 0
        for c in data:
            cv = c.encode('utf-8')

            if pos + len(cv) > len(self.__buffer):
                raise ValueError('overflow')

            self.__buffer[pos:pos+len(cv)] = cv
            pos += len(cv)

        self.__len_courant = pos

    def set_text_read(self, data):
        try:
            if len(data) > len(self.__buffer):
                raise ValueError('overflow')
        except TypeError:
            pass  # Pas de len sur data

        pos = 0
        c = data.read(1)
        while c != '':
            cv = c.encode('utf-8')

            if pos + len(cv) > len(self.__buffer):
                raise ValueError('overflow')

            self.__buffer[pos:pos+len(cv)] = cv
            pos += len(cv)
            c = data.read(1)

        self.__len_courant = pos

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
        # self.__buffer.clear()

    def write(self, data):
        if len(data) + self.__len_courant > len(self.__buffer):
            raise Exception('ouverflow')

        if isinstance(data, bytes) or isinstance(data, bytearray):
            self.__buffer[self.__len_courant:self.__len_courant+len(data)] = data
            self.__len_courant += len(data)
        elif isinstance(data, str):
            for c in data:
                cb = c.encode('utf-8')
                self.write(cb)
        else:
            raise ValueError("non supporte %s" % data)

    @property
    def buffer(self):
        return self.__buffer

    def __iter__(self):
        for i in range(0, self.__len_courant):
            yield self.__buffer[i]

    def __len__(self):
        return self.__len_courant


# Changements 2023.5 - nouveau format de message (similaire a nostr)
# {pubkey, estampille, kind, contenu, routage, pre-migration, id, sig}
# id = blake2s(json.dumps([pubkey, estampille, kind, contenu, routage?, pre-migration?]))
# sig = ed25519.sign(pubkey, id)
# valeurs binaires proviennent de binascii.hexlify(BIN).decode('utf-8')

async def signer_message_2023_5(id_message: str, cle_privee=None):
    cle_publique = None
    if cle_privee is None:
        # Charger la cle locale
        try:
            with open(certificat.PATH_CLE_PRIVEE, 'rb') as fichier:
                cle_privee = fichier.read()
            if len(cle_privee) == 64:
                # Split cle privee/publique
                cle_publique = cle_privee[32:]
                cle_privee = cle_privee[:32]
        except OSError:
            print("Cle prive absente, utiliser .new")
            with open(certificat.PATH_CLE_PRIVEE + '.new', 'rb') as fichier:
                cle_privee = fichier.read()

    ticks_debut = time.ticks_ms()
    if cle_publique is None:
        # Deriver la cle publique a partir de la cle privee
        cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)
    print("Cle publique : %s" % binascii.hexlify(cle_publique))
    print("signer_message_2023_5 ed25519generatepubkey duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    await asyncio.sleep_ms(1)

    hachage = binascii.unhexlify(id_message)

    ticks_debut = time.ticks_ms()
    signature = oryx_crypto.ed25519sign(cle_privee, cle_publique, hachage)
    print("__signer_message_2 ed25519sign duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))

    await asyncio.sleep_ms(1)
    #signature = multibase.encode('base64', signature)
    signature = binascii.hexlify(signature).decode('utf-8')
    
    return signature


def verifier_signature_2023_5(id_message: str, signature: str, cle_publique: str):
    """ Verifie la signature d'un message. Lance une exception en cas de signature invalide. """
    hachage = binascii.unhexlify(id_message)
    cle_publique = binascii.unhexlify(cle_publique)
    signature = binascii.unhexlify(signature)
    ticks_debut = time.ticks_ms()
    oryx_crypto.ed25519verify(cle_publique, signature, hachage)
    print("__verifier_signature ed25519verify duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))


def hacher_message_2023_5(message: dict, buffer=None):
    ticks_debut = time.ticks_ms()
    message_array = preparer_array_hachage_2023_5(message)
    hachage = oryx_crypto.blake2s(message_stringify(message_array, buffer=buffer))
    print("hacher_message stringify+blake2s duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    return binascii.hexlify(hachage).decode('utf-8')


def preparer_array_hachage_2023_5(message) -> list:
    kind = message['kind']
    
    message_array = [
        message['pubkey'],
        message['estampille'],
        message['kind'],
        message['contenu'],
    ]

    if kind in [1, 2, 3, 5, 7]:
        routage = prep_message_1(message['routage'])
        message_array.append(routage)
    if kind in [7]:
        message_array.append(message['pre-migration'])
    
    if kind > 7:
        raise Error('kind message non supporte' % kind)

    return message_array
