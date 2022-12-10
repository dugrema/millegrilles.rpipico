CONST_PATH_FICHIER_CONN = const('conn.json')

CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_CHARGER_URL_RELAIS = const(3)
CONST_MODE_SIGNER_CERTIFICAT = const(4)
CONST_MODE_POLLING = const(99)

CONST_CHAMP_HTTP_INSTANCE = const('http_instance')

async def detecter_mode_operation():
    from os import stat
    # Si wifi.txt/idmg.txt manquants, on est en mode initial.
    try:
        stat(CONST_PATH_FICHIER_CONN)
    except:
        print("Mode initialisation")
        return CONST_MODE_INIT
    
    try:
        stat('certs/ca.der')
    except:
        print("Mode recuperer ca.der")
        return CONST_MODE_RECUPERER_CA
    
    try:
        stat("certs/cert.pem")
    except:
        print("Mode signer certificat")
        return CONST_MODE_SIGNER_CERTIFICAT

    return CONST_MODE_POLLING  # Mode polling


async def initialisation():
    """
    Mode initial si aucun parametres charges
    """
    await led_executer_sequence(CODE_CONFIG_INITIALISATION, executions=None)


async def initialiser_wifi():
    from wifi import connect_wifi
    
    wifi_ok = False
    for _ in range(0, 5):
        try:
            status = await connect_wifi()
            return status
        except (RuntimeError, OSError) as e:
            print("Wifi error %s" % e)
            await asyncio.sleep(3)
    if wifi_ok is False:
        raise RuntimeError('wifi')
            

async def recuperer_ca():
    from certificat import sauvegarder_ca
    
    print("Init millegrille")
    idmg = get_idmg()
    fiche = await charger_fiche()
    del fiche['_millegrille']
    
    if fiche['idmg'] != idmg:
        raise Exception('IDMG mismatch')
    
    print("IDMG OK : %s" % idmg)
    
    # Sauvegarder le certificat CA
    sauvegarder_ca(fiche['ca'], idmg)


async def init_cle_privee(force=False):
    from os import stat
    from certificat import PATH_CLE_PRIVEE, generer_cle_secrete
    try:
        stat(PATH_CLE_PRIVEE)
    except OSError:
        generer_cle_secrete()
        print("Cle privee initialisee")


def get_url_instance():
    from json import load
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return load(fichier)[CONST_CHAMP_HTTP_INSTANCE]


def get_http_timeout():
    from json import load
    try:
        with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
            return load(fichier)['http_timeout']
    except Exception:
        pass
    
    return CONST_HTTP_TIMEOUT_DEFAULT


def get_idmg():
    from json import load
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return load(fichier)['idmg']


def get_user_id():
    from json import load
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return load(fichier)['user_id']


# Recuperer la fiche (CA, chiffrage, etc)
async def charger_fiche():
    import urequests2 as requests
    import uasyncio as asyncio
    
    try:
        fiche_url = get_url_instance() + '/fiche.json'
    except OSError:
        print("Fichier connexion absent")
        return

    # Downloader la fiche
    # print("Recuperer fiche a %s" % fiche_url)
    fiche_json = None
    reponse = await requests.get(fiche_url)
    try:
        await asyncio.sleep(0)  # Yield
        if reponse.status_code != 200:
            raise Exception("fiche http status:%d" % reponse.status_code)
        fiche_json = await reponse.json()
        # print("Fiche recue\n%s" % fiche_json)
    finally:
        reponse.close()
        
    return fiche_json
