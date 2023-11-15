import time

import oryx_crypto

from binascii import hexlify, unhexlify
from json import dumps

from millegrilles.certificat import rnd_bytes, get_fingerprint_local
from millegrilles.message_inscription import NOM_APPAREIL

EXPIRATION_SECRET = const(6*3600)


class ChiffrageMessages:

    def __init__(self):
        self.__cle_privee_echange = None
        self.__secret_echange = None
        self.__expiration_secret_echange = None
        self.__uuid_appareil = None
        self.__fingerprint_local = None

    def clear(self):
        self.__cle_privee_echange = None
        self.__secret_echange = None
        self.__expiration_secret_echange = None
        self.__uuid_appareil = None
        self.__fingerprint_local = None

    def generer_cle(self) -> str:
        if self.__cle_privee_echange is None:
            self.__cle_privee_echange = rnd_bytes(32)
        cle_publique = oryx_crypto.x25519generatepubkey(self.__cle_privee_echange)
        cle_publique = hexlify(cle_publique).decode('utf-8')
        return cle_publique

    def charger_info_certificat(self):
        self.__fingerprint_local = get_fingerprint_local()
        self.__uuid_appareil = NOM_APPAREIL

    def calculer_secret_exchange(self, cle_publique: str):
        if self.__cle_privee_echange is None:
            raise Error('cle privee None')

        cle_publique_remote = unhexlify(cle_publique.encode('utf-8'))
        self.__secret_echange = oryx_crypto.x25519computesharedsecret(self.__cle_privee_echange, cle_publique_remote)

        # print("!!! SECRET !!! : %s" % hexlify(self.__secret_echange))

        # Cleanup
        self.__cle_privee_echange = None
        self.charger_info_certificat()

        # Mettre date d'expiration de la cle secrete
        self.__expiration_secret_echange = time.time() + EXPIRATION_SECRET

    def doit_renouveler_secret(self):
        if self.__secret_echange is None:
            return True

        return time.time() < self.__expiration_secret_echange

    @property
    def pret(self):
        return self.__secret_echange is not None

    async def chiffrer(self, message: dict):
        message = dumps(message)
        return {
            'uuid_appareil': self.__uuid_appareil,
            'fingerprint': self.__fingerprint_local,
            'nonce': '--nonce--',
            'tag': '--tag--',
            'message_chiffre': message,
        }
