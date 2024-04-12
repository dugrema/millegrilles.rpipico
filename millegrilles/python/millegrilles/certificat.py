import binascii
import oryx_crypto
import time
import uasyncio as asyncio

from os import mkdir, remove
from math import ceil
from struct import pack
from random import getrandbits

from multiformats import multihash, multibase

MARQUEUR_END_CERTIFICATE = const(b'-----END CERTIFICATE-----')
CONST_HACHAGE_FINGERPRINT = const('blake2s-256')

OID_EXCHANGES = bytearray([0x2a, 0x03, 0x04, 0x00])
OID_ROLES = bytearray([0x2a, 0x03, 0x04, 0x01])
OID_DOMAINES = bytearray([0x2a, 0x03, 0x04, 0x02])
OID_USER_ID = bytearray([0x2a, 0x03, 0x04, 0x03])

# CONST_CACHE_ACCES = const('_cache_acces')
# CONST_CACHE_HIGH_LEN = const(7)
# CONST_CACHE_MAX_LEN = const(20)

PATHNAME_RENOUVELER = const('/renouveler')

PATH_CERTS = const('certs')
PATH_CA_CERT = const('certs/ca.der')
PATH_CLE_PRIVEE = const('certs/secret.key')
PATH_CERT = const('certs/cert.pem')

IDMG_VERSION_ACTIVE = const(2)


# Cache pour certains certificats
# CACHE_DICT = dict()


def rnd_bytes(nb_bytes):
    bytes_courant = nb_bytes
    rnd_val = bytes()
    while bytes_courant > 0:
        bytes_courant -= 4
        rnd_bits = getrandbits(32)  # 4 bytes
        rnd_val += bytes(pack('L', rnd_bits))
    
    return rnd_val[:nb_bytes]


def calculer_fingerprint(contenu_der):
    """ Calculer le fingerprint d'un certificat """
    x509_info = oryx_crypto.x509certificatinfo(contenu_der)
    # Nouveau calcul 2023.5 : la cle publique ed25519 est le fingerprint
    public_key = oryx_crypto.x509PublicKey(x509_info)
    fingerprint = binascii.hexlify(public_key).decode('utf-8')
    
    return fingerprint


def calculer_idmg(ca_der):
    x509_info = oryx_crypto.x509certificatinfo(ca_der)
    
    fingerprint = oryx_crypto.blake2s(ca_der)
    fingerprint = multihash.wrap(CONST_HACHAGE_FINGERPRINT, fingerprint)

    date_expiration = oryx_crypto.x509EndDate(x509_info)
    date_expiration = float(date_expiration) / 1000.0
    date_expiration = ceil(date_expiration)
    date_expiration = int(date_expiration)
    
    IDMG_VERSION_PACK = '<BI'
    
    valeur_combinee = pack(IDMG_VERSION_PACK, IDMG_VERSION_ACTIVE, date_expiration)
    valeur_combinee = valeur_combinee + fingerprint
    
    return multibase.encode('base58btc', bytes(valeur_combinee))


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


def get_certificat_local():
    try:
        with open(PATH_CERT, 'r') as fichier:
            return fichier.read()
        #return load_pem_certificat(PATH_CERT)
    except OSError:
        return None


async def valider_certificats(pem_certs: list, date_validation=None, is_der=False, fingerprint=None, err_ca_ok=False):
    """ Valide la chaine de certificats, incluant le dernier avec le CA.
        @return Information du certificat leaf
        @raises Exception Si la chaine est invalide. """
    # global CACHE_DICT

    if date_validation is None:
        date_validation = time.time()
    elif date_validation is False:
        date_validation = 0  # Invalide la date
    # print("valider_certificats avec time %s" % date_validation)

    # Verifier si le certificat est dans le cache memoire
    # if fingerprint is not None:
    #     if CACHE_DICT.get(fingerprint) is not None:
    #         #print("Cert Cache HIT %s", fingerprint)
    #         if date_validation is not None:
    #             # TODO : Valider la date - note : un certificat en cache doit etre presentement valide
    #             pass
    #         enveloppe = CACHE_DICT[fingerprint]
    #         enveloppe[CONST_CACHE_ACCES] += 1  # Incrementer nombre d'acces, cache est most commonly used
    #         return enveloppe
    #     #else:
    #     #    print("Cert Cache MISS %s", fingerprint)

    cert = pem_certs.pop(0)
    if is_der is False:
        cert = oryx_crypto.x509readpemcertificate(cert)
    
    # Conserver l'information du certificat leaf
    x509_info = oryx_crypto.x509certificatinfo(cert)
    fingerprint = calculer_fingerprint(cert)
    asyncio.sleep_ms(10)  # Yield

    enveloppe = {
        'fingerprint': fingerprint,
        'public_key': oryx_crypto.x509PublicKey(x509_info),
        'expiration': oryx_crypto.x509EndDate(x509_info),
        # 'exchanges': exchanges,
        # 'roles': roles,
        # 'domaines': domaines,
        # 'user_id': user_id,
    }

    # Parcourir la chaine. Valider le dernier certificat avec le CA
    while len(pem_certs) > 0:
        parent = pem_certs.pop(0)
        if is_der is False:
            parent = oryx_crypto.x509readpemcertificate(parent)
        asyncio.sleep_ms(10)  # Yield
        oryx_crypto.x509validercertificate(cert, parent, date_validation)
        cert = parent  # Poursuivre la chaine
    else:
        try:
            with open(PATH_CA_CERT, 'rb') as fichier:
                parent = fichier.read()
            asyncio.sleep_ms(10)  # Yield
            oryx_crypto.x509validercertificate(cert, parent, date_validation)
        except OSError as e:
            if e.errno == 2:
                if err_ca_ok is True:
                    # Ok, CA absent
                    enveloppe['err'] = 'CA absent'
                else:
                    raise e
            else:
                raise e

    exchanges = oryx_crypto.x509Extension(x509_info, OID_EXCHANGES)
    if exchanges is not None:
        exchanges = exchanges.split(',')
        enveloppe['exchanges'] = exchanges
        
    roles = oryx_crypto.x509Extension(x509_info, OID_ROLES)
    if roles is not None:
        roles = roles.split(',')
        enveloppe['roles'] = roles
        
    domaines = oryx_crypto.x509Extension(x509_info, OID_DOMAINES)
    if domaines is not None:
        domaines = domaines.split(',')
        enveloppe['domaines'] = domaines
        
    user_id = oryx_crypto.x509Extension(x509_info, OID_USER_ID)
    if user_id is not None:
        enveloppe['user_id'] = user_id
    
    # # Verifier si on conserve le certificat dans le cache
    # if len(CACHE_DICT) < CONST_CACHE_MAX_LEN:  # Limite d'elements concurrents dans le cache (cleanup va reduire la taille)
    #     if 'senseurspassifs' in roles or \
    #        'senseurspassifs_relai' in roles or \
    #        'maitredescles' in roles or \
    #        'core' in roles:
    #         # Verifier si le certificat est presentement valide - requis pour mettre en cache
    #         if enveloppe['expiration'] > time.time():
    #             enveloppe[CONST_CACHE_ACCES] = 1
    #             CACHE_DICT[fingerprint] = enveloppe
    
    return enveloppe


def sauvegarder_ca(ca_pem, idmg=None):
    try:
        mkdir(PATH_CERTS)
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


def generer_cle_secrete(inclure_publique=False):
    cle_privee = rnd_bytes(32)
    cle_publique = oryx_crypto.ed25519generatepubkey(cle_privee)
    with open(PATH_CLE_PRIVEE + '.new', 'wb') as fichier:
        fichier.write(cle_privee)    # Premiers 32 bytes
        fichier.write(cle_publique)  # Derniers 32 bytes

    # Cleanup, retirer certs/cert.pem.new si present
    try:
        remove(PATH_CERT + '.new')
    except OSError:
        pass
    
    if inclure_publique is True:
        return cle_privee, cle_publique
    
    return cle_privee


def charger_cle_privee(path_cle = PATH_CLE_PRIVEE):
    # print('Charger cle privee %s pour conversion publique' % path_cle)
    try:
        with open(path_cle, 'rb') as fichier:
            cle_privee = fichier.read()
    except OSError:
        with open(path_cle + '.new', 'rb') as fichier:
            cle_privee = fichier.read()
        
    return cle_privee[:32]


def charger_cle_publique(path_cle = PATH_CLE_PRIVEE):
    # print('Charger cle privee %s pour conversion publique' % path_cle)
    try:
        with open(path_cle, 'rb') as fichier:
            cle_privee = fichier.read()
    except OSError:
        with open(path_cle + '.new', 'rb') as fichier:
            cle_privee = fichier.read()
        
    if len(cle_privee) == 64:
        # La cle publique est deja calculee
        return cle_privee[32:]
    
    # Calculer la cle publique
    return oryx_crypto.ed25519generatepubkey(cle_privee)


def get_fingerprint_local():
    cle_publique = charger_cle_publique()
    return binascii.hexlify(cle_publique).decode('utf-8')


def get_userid_local():
    cert_local = split_pem(get_certificat_local())[0]
    x509_info = oryx_crypto.x509certificatinfo(cert_local)
    return oryx_crypto.x509Extension(x509_info, OID_USER_ID)


def get_expiration_certificat_local():
    try:
        with open(PATH_CERT, 'rb') as fichier:
            certificat = fichier.read()
    except OSError:
        return None, None

    certificat = certificat.split(MARQUEUR_END_CERTIFICATE)[0] + MARQUEUR_END_CERTIFICATE
    contenu = oryx_crypto.x509readpemcertificate(certificat)
    cert_info = oryx_crypto.x509certificatinfo(contenu)
    
    return oryx_crypto.x509EndDate(cert_info), oryx_crypto.x509PublicKey(cert_info)


def remove_certificate():
    try:
        remove(PATH_CLE_PRIVEE)
    except OSError:
        pass
    try:
        remove(PATH_CERT)
    except OSError:
        pass


def remove_ca():
    try:
        remove(PATH_CA_CERT)
    except OSError:
        pass


async def entretien_certificat():
    # global CACHE_DICT

    date_expiration, cle_publique = get_expiration_certificat_local()
    print("Date expiration cert : %s" % date_expiration)

    if date_expiration is None:
        print("Certificat absent / expire")
        return False

    # Verifier correpondance cles
    try:
        if cle_publique != charger_cle_publique():
            print("Mismatch cert et cle privee, RESET")
            remove_certificate()
            return False
    except OSError:
        print("Erreur verification cle privee/cert, RESET")
        remove_certificate()
        return False    
    
    # Verifier date d'expiration
    if time.time() > date_expiration:
        print("Certificat expire - nettoyage")
        remove_certificate()
        return False
    
    # # Entretien cache
    # if len(CACHE_DICT) > CONST_CACHE_HIGH_LEN:
    #     # Trier entrees de cache
    #     cache_values = sort(CACHE_DICT.values(), reverse=True, key=cache_sort_key)
    #     # Conserver les N premieres entrees
    #     CACHE_DICT = cache_values[0:CONST_CACHE_HIGH_LEN]

    return True


def cache_sort_key(elem):
    return elem[CONST_CACHE_ACCES]
