# Test PEM
import binascii
import json
import math
import time
import uasyncio as asyncio
import oryx_crypto

from io import IOBase

from . import certificat
# -- DEV --
#from millegrilles import certificat
# -- DEV --

from collections import OrderedDict


VERSION_SIGNATURE = 2

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


async def verifier_message(message: dict, buffer=None, err_ca_ok=False):
    # Valider le certificat - raise Exception si erreur
    pubkey = message['pubkey']

    await asyncio.sleep_ms(1)
    ticks_debut = time.ticks_ms()
    info_certificat = await certificat.valider_certificats(message['certificat'], err_ca_ok=err_ca_ok)  #, fingerprint=message['pubkey'])
    print("verifier_message verifier certificat duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    del message['certificat']
    await asyncio.sleep_ms(1)

    # Verifier la signature du message
    signature = message['sig']
    id_message = message['id']
    # Raise une exception si la signature est invalide
    verifier_signature_2023_5(id_message, signature, pubkey)
    await asyncio.sleep_ms(1)

    # Hacher le message, comparer id
    id_calcule = await hacher_message_2023_5(message, buffer=buffer)
    if id_calcule != id_message:
        print('Mismatch, id_calcule : %s, id_message : %s' % (id_calcule, id_message))
        raise Exception('Mismatch id message')

    await asyncio.sleep_ms(1)

    return info_certificat


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
                if len(cle_privee) == 64:
                    # Split cle privee/publique
                    cle_publique = cle_privee[32:]
                    cle_privee = cle_privee[:32]

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


async def hacher_message_2023_5(message: dict, buffer=None):
    ticks_debut = time.ticks_ms()
    await asyncio.sleep_ms(1)
    message_array = preparer_array_hachage_2023_5(message)
    await asyncio.sleep_ms(1)

    hachage = oryx_crypto.blake2s(message_stringify(message_array, buffer=buffer))
    print("hacher_message stringify+blake2s duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
    await asyncio.sleep_ms(1)

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

async def formatter_message(message: dict, kind: int, domaine=None, action=None, partition=None, cle_privee=None, buffer=None, ajouter_certificat=True):
    """ Formatte un message avec estampille, hachage (id) et signature (sig) """
    
    if cle_privee is not None:
        # Calculer pubkey
        pubkey = binascii.hexlify(oryx_crypto.ed25519generatepubkey(cle_privee)).decode('utf-8')
    else:
        pubkey = binascii.hexlify(certificat.charger_cle_publique()).decode('utf-8')

    # Serialiser le contenu en string
    contenu = prep_message_1(message)
    contenu = message_stringify(contenu).decode('utf-8')

    enveloppe_message = {
        'pubkey': pubkey,
        'estampille': time.time(),
        'kind': kind,
        'contenu': contenu,
    }
    
    if kind in [1, 2, 3, 5]:
        routage = dict()
        if action is not None:
            routage['action'] = action
        if domaine is not None:
            routage['domaine'] = domaine
        if partition is not None:
            routage['partition'] = partition
        enveloppe_message['routage'] = routage

    if kind > 6:
        raise Exception('kind %d non supporte' % kind)
    
    hachage_message = await hacher_message_2023_5(enveloppe_message, buffer)
    enveloppe_message['id'] = hachage_message
    
    signature = await signer_message_2023_5(hachage_message, cle_privee)
    enveloppe_message['sig'] = signature
    
    if ajouter_certificat is True:
        enveloppe_message['certificat'] = certificat.split_pem(certificat.get_certificat_local(), format_str=True)

    return enveloppe_message

