import binascii
# import json
# import math
import time
import uasyncio as asyncio
import oryx_crypto
from . import certificat
# om io import IOBase

from .mgmessages import message_stringify, prep_message_1


# Changements 2023.5 - nouveau format de message (similaire a nostr)
# {pubkey, estampille, kind, contenu, routage, pre-migration, id, sig}
# id = blake2s(json.dumps([pubkey, estampille, kind, contenu, routage?, pre-migration?]))
# sig = ed25519.sign(pubkey, id)
# valeurs binaires proviennent de binascii.hexlify(BIN).decode('utf-8')
class Cryptographie:

    def __init__(self, watchdog, chiffrage):
        self.__watchdog = watchdog      # watchdog.Watchdog
        self.__chiffrage = chiffrage    # chiffrage.ChiffrageMessages

    async def verifier_message(self, message: dict, buffer=None, err_ca_ok=False):
        # Valider le certificat - raise Exception si erreur
        pubkey = message['pubkey']

        try:
            # await asyncio.sleep_ms(1)
            await self.__watchdog.yield_duration(1)
            ticks_debut = time.ticks_ms()
            info_certificat = await certificat.valider_certificats(self.__watchdog, message['certificat'], fingerprint=pubkey,
                                                                   err_ca_ok=err_ca_ok)  # , fingerprint=message['pubkey'])
            self.__watchdog.feed()
            print("verifier_message verifier certificat %s duree %d" % (pubkey,
                                                                        time.ticks_diff(time.ticks_ms(), ticks_debut)))
            del message['certificat']
            await self.__watchdog.yield_duration(1)
        except KeyError as ke:
            self.__watchdog.feed()
            if err_ca_ok is True:
                info_certificat = True
            else:
                raise ke

        # Verifier la signature du message
        signature = message['sig']
        id_message = message['id']
        # Raise une exception si la signature est invalide
        await self.__watchdog.yield_duration(1)
        self.verifier_signature_2023_5(id_message, signature, pubkey)
        # await asyncio.sleep_ms(1)
        self.__watchdog.feed()
        await self.__watchdog.yield_duration(1)

        # Hacher le message, comparer id
        self.__watchdog.feed()
        id_calcule = await self.hacher_message_2023_5(message, buffer=buffer)
        self.__watchdog.feed()
        if id_calcule != id_message:
            print('Mismatch, id_calcule : %s, id_message : %s' % (id_calcule, id_message))
            raise Exception('Mismatch id message')

        # await asyncio.sleep_ms(1)
        await self.__watchdog.yield_duration(1)

        return info_certificat

    async def signer_message_2023_5(self, id_message: str, cle_privee=None):
        cle_publique = None
        self.__watchdog.feed()
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

        await self.__watchdog.yield_duration(1)
        ticks_debut = time.ticks_ms()
        if cle_publique is None:
            # Deriver la cle publique a partir de la cle privee
            cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)
            self.__watchdog.feed()
            await self.__watchdog.yield_duration(1)
        print("Cle publique : %s" % binascii.hexlify(cle_publique))
        print("signer_message_2023_5 ed25519generatepubkey duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
        # await asyncio.sleep_ms(1)
        await self.__watchdog.yield_duration(1)

        hachage = binascii.unhexlify(id_message)
        self.__watchdog.feed()

        ticks_debut = time.ticks_ms()
        self.__watchdog.feed()
        signature = oryx_crypto.ed25519sign(cle_privee, cle_publique, hachage)
        self.__watchdog.feed()
        print("__signer_message_2 ed25519sign duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))

        # await asyncio.sleep_ms(1)
        await self.__watchdog.yield_duration(1)
        # signature = multibase.encode('base64', signature)
        signature = binascii.hexlify(signature).decode('utf-8')

        return signature

    def verifier_signature_2023_5(self, id_message: str, signature: str, cle_publique: str):
        """ Verifie la signature d'un message. Lance une exception en cas de signature invalide. """
        hachage = binascii.unhexlify(id_message)
        cle_publique = binascii.unhexlify(cle_publique)
        signature = binascii.unhexlify(signature)
        ticks_debut = time.ticks_ms()
        self.__watchdog.feed()
        oryx_crypto.ed25519verify(cle_publique, signature, hachage)
        self.__watchdog.feed()
        print("__verifier_signature ed25519verify duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))

    async def hacher_message_2023_5(self, message: dict, buffer=None):
        ticks_debut = time.ticks_ms()
        # await asyncio.sleep_ms(1)
        await self.__watchdog.yield_duration(1)
        message_array = self.preparer_array_hachage_2023_5(message)
        self.__watchdog.feed()
        # await asyncio.sleep_ms(1)
        await self.__watchdog.yield_duration(1)

        self.__watchdog.feed()
        hachage = oryx_crypto.blake2s(message_stringify(message_array, buffer=buffer))
        self.__watchdog.feed()
        print("hacher_message stringify+blake2s duree %d" % time.ticks_diff(time.ticks_ms(), ticks_debut))
        # await asyncio.sleep_ms(1)
        await self.__watchdog.yield_duration(1)

        return binascii.hexlify(hachage).decode('utf-8')

    def preparer_array_hachage_2023_5(self, message) -> list:
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
            raise Error('kind message non supporte %s' % kind)

        return message_array

    async def formatter_message(self, message: dict, kind: int, domaine=None, action=None, partition=None,
                                cle_privee=None, buffer=None, ajouter_certificat=True):
        """ Formatte un message avec estampille, hachage (id) et signature (sig) """
        print("Formatter message")
        if not isinstance(message, dict):
            raise Exception("Not dict")

        if cle_privee is not None:
            # Calculer pubkey
            pubkey = binascii.hexlify(oryx_crypto.ed25519generatepubkey(cle_privee)).decode('utf-8')
        else:
            pubkey = binascii.hexlify(certificat.charger_cle_publique()).decode('utf-8')

        # Serialiser le contenu en string
        self.__watchdog.feed()
        print("prep 1")
        contenu = prep_message_1(message)
        self.__watchdog.feed()
        print("prep stringify")
        contenu = message_stringify(contenu).decode('utf-8')
        await self.__watchdog.yield_duration(1)

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

        print("hacher")
        hachage_message = await self.hacher_message_2023_5(enveloppe_message, buffer)
        enveloppe_message['id'] = hachage_message

        print("signer")
        signature = await self.signer_message_2023_5(hachage_message, cle_privee)
        enveloppe_message['sig'] = signature

        if ajouter_certificat:
            enveloppe_message['certificat'] = certificat.split_pem(certificat.get_certificat_local(), format_str=True)
            self.__watchdog.feed()

        print("Formatter message done")
        return enveloppe_message
