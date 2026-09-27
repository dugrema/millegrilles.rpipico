# Test PEM
import json
import math
import uasyncio as asyncio

from io import IOBase
from collections import OrderedDict

from millegrilles.mgthreads import dump_spawn
from millegrilles.watchdog import Watchdog

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


async def message_stringify(watchdog, message, buffer=None):
    if buffer is None:
        return json.dumps(message, separators=(',', ':')).encode('utf-8')
    else:
        buffer.clear()
        #watchdog.feed()
        #json.dump(message, buffer, separators=(',', ':'))
        #watchdog.feed()
        await dump_spawn(watchdog, message, buffer, separators=(',', ':'))
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
        self.__len = 0
        self.__pos = 0
        self.__lock = asyncio.Lock()

    def reset(self):
        self.__len = 0
        self.__pos = 0

    def write(self, data):
        n = len(data)
        if self.__len + n > len(self.__buffer):
            raise OverflowError('overflow')
        if isinstance(data, bytes) or isinstance(data, bytearray) or isinstance(data, memoryview):
            self.__buffer[self.__len : self.__len + n] = data
            self.__len += n
        else:
            raise Exception('Unsupported data type')
        return n

    def readinto(self, buf):
        if self.__pos >= self.__len:
            return 0  # EOF
        chunk_len = min(len(buf), self.__len - self.__pos)
        buf[:chunk_len] = memoryview(self.__buffer)[self.__pos : self.__pos + chunk_len]
        self.__pos += chunk_len
        return chunk_len

    def read(self, size=-1):
        if self.__pos >= self.__len:
            return b""
        if size < 0 or size > (self.__len - self.__pos):
            size = self.__len - self.__pos
        res = bytes(memoryview(self.__buffer)[self.__pos : self.__pos + size])
        self.__pos += size
        return res

    def get_data(self):
        return memoryview(self.__buffer)[:self.__len]

    def set_text(self, data):
        if not isinstance(data, str):
            raise Exception('Unsupported data type')
        # print('Buffer setText', end="")
        # print(data)
        self.clear()
        self.write(data.encode('utf-8'))  # Shortcut, may use a lot of memory
        # try:
        #     if len(data) > len(self.__buffer):
        #         raise ValueError('overflow')
        # except TypeError:
        #     pass  # Pas de len sur data
        # pos = 0
        # for c in data:
        #     cv = c.encode('utf-8')
        #
        #     if pos + len(cv) > len(self.__buffer):
        #         raise ValueError('overflow')
        #
        #     self.__buffer[pos:pos+len(cv)] = cv
        #     pos += len(cv)
        #
        # self.__len = pos

    # def set_text_read(self, data):
    #     try:
    #         if len(data) > len(self.__buffer):
    #             raise ValueError('overflow')
    #     except TypeError:
    #         pass  # Pas de len sur data
    #
    #     pos = 0
    #     c = data.read(1)
    #     while c != '':
    #         cv = c.encode('utf-8')
    #
    #         if pos + len(cv) > len(self.__buffer):
    #             raise ValueError('overflow')
    #
    #         self.__buffer[pos:pos+len(cv)] = cv
    #         pos += len(cv)
    #         c = data.read(1)
    #
    #     self.__len = pos

    def set_bytes(self, data):
        if not isinstance(data, bytes) and not isinstance(data, bytearray) and not isinstance(data, memoryview):
            raise Exception("Unsupported data type")
        if len(data) > len(self.__buffer):
            raise ValueError('overflow')

        self.clear()
        self.write(data)

        # self.__len = len(data)
        # self.__buffer[:self.__len] = data

    def set_len(self, len_data):
        if len_data > len(self.__buffer):
            raise ValueError('overflow')
        self.__len = len_data

    def clear(self):
        self.__len = 0
        self.__pos = 0
        # self.__buffer.clear()

    # def write(self, data):
    #     if len(data) + self.__len > len(self.__buffer):
    #         raise Exception('ouverflow')
    #
    #     if isinstance(data, bytes) or isinstance(data, bytearray):
    #         self.__buffer[self.__len:self.__len + len(data)] = data
    #         self.__len += len(data)
    #     elif isinstance(data, str):
    #         for c in data:
    #             cb = c.encode('utf-8')
    #             self.write(cb)
    #     else:
    #         raise ValueError("non supporte %s" % data)

    @property
    def buffer(self):
        return self.__buffer

    def __iter__(self):
        for i in range(0, self.__len):
            yield self.__buffer[i]

    def __len__(self):
        return self.__len

    async def __aenter__(self):
        await self.__lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__lock.release()
        return False
