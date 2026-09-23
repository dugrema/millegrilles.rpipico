# Test PEM
import json
import math
import uasyncio as asyncio

from io import IOBase
from collections import OrderedDict

#from . import certificat
# -- DEV --
#from millegrilles import certificat
# -- DEV --


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
