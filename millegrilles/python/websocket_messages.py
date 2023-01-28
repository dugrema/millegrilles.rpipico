import time
import uasyncio as asyncio

from json import dumps, loads, load, dump
from gc import collect
from sys import print_exception
from micropython import mem_info

from uwebsockets.client import connect
from millegrilles.certificat import get_expiration_certificat_local
from millegrilles.mgmessages import signer_message, verifier_message
from handler_commandes import traiter_commande
from config import get_http_timeout, charger_relais, set_configuration_display, \
     get_timezone, generer_message_timeinfo

from message_inscription import verifier_renouveler_certificat_ws

PATHNAME_POLL = const('/poll')
PATHNAME_REQUETE = const('/requete')
CONST_CHAMP_TIMEOUT = const('http_timeout')

CONST_DOMAINE_SENSEURSPASSIFS = const('SenseursPassifs')
CONST_REQUETE_DISPLAY = const('getAppareilDisplayConfiguration')
CONST_REQUETE_FICHE_PUBLIQUE = const('getFichePublique')
CONST_REQUETE_RELAIS_WEB = const('getRelaisWeb')

CONST_DUREE_THREAD_POLLING = const(6 * 60 * 60)
CONST_EXPIRATION_CONFIG = const(10 * 60)


class HttpErrorException(Exception):
    pass


async def __preparer_message(timeout_http, generer_etat, buffer):
    # Genrer etat
    if generer_etat is not None:
        etat = await generer_etat()
    else:
        etat = {'lectures_senseurs': {}}
        
    # Ajouter timeout pour limite polling
    etat[CONST_CHAMP_TIMEOUT] = timeout_http

    # Signer message
    etat = await signer_message(
        etat, domaine=CONST_DOMAINE_SENSEURSPASSIFS, action='etatAppareil', buffer=buffer)
    buffer.clear()
    dump(etat, buffer)

    return buffer


async def poll(websocket, buffer, timeout_http=60, generer_etat=None, ui_lock=None):
    buffer = await __preparer_message(timeout_http, generer_etat, buffer)

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    print("Taille etat: %d" % len(buffer))
    await asyncio.sleep_ms(1)

    # Emettre etat
    websocket.send(buffer.get_data())
    await asyncio.sleep_ms(1)  # Yield

    # Calculer limite de la periode de polling
    if timeout_http is None or timeout_http < 1:
        timeout_http = 1  # Min pour executer entretien websocket
    expiration_polling = time.time() + timeout_http

    # Poll socket
    while expiration_polling > time.time():
        try:
            reponse = await websocket.recv(buffer.buffer)
            if reponse is not None and len(reponse) > 0:
                print("Reponse buffer taille %d" % len(reponse))
                return reponse
        except OSError as e:
            if e.errno == -110:
                pass  # Socket timeout (OK)
            else:
                raise e
        
        # Intervalle polling socket
        await asyncio.sleep_ms(100)


async def requete_configuration_displays(websocket, buffer):
    requete = await signer_message(
        dict(), domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_DISPLAY)
    buffer.set_text(dumps(requete))
    requete = None

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    websocket.send(buffer.get_data())


async def requete_fiche_publique(websocket, buffer):
    requete = await signer_message(
        dict(), domaine='senseurspassifs_relai', action=CONST_REQUETE_FICHE_PUBLIQUE)
    buffer.set_text(dumps(requete))
    requete = None

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    websocket.send(buffer.get_data())


async def requete_relais_web(websocket, buffer):
    requete = await signer_message(
        dict(), domaine='senseurspassifs_relai', action=CONST_REQUETE_RELAIS_WEB, buffer=buffer)
    buffer.clear()
    dump(requete, buffer)
    requete = None

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    websocket.send(buffer.get_data())
    
    

async def charger_timeinfo(websocket, buffer, refresh: False):
    
    offset_info = None
    try:
        with open('tzoffset.json', 'rb') as fichier:
            offset_info = load(fichier)
            if refresh is False:
                return offset_info['offset']
    except OSError:
        print('tzoffset.json absent')
    except KeyError:
        print('tzoffset.json erreur contenu')

    if offset_info is None:
        # Generer fichier dummy
        offset_info = {'offset': 0}
        with open('tzoffset.json', 'wb') as fichier:
            dump(offset_info, fichier)

    timezone_str = get_timezone()
    if timezone_str is not None:
        print("Charger information timezone %s" % timezone_str)
        buffer.set_text(dumps(await generer_message_timeinfo(timezone_str)))
        
        await asyncio.sleep_ms(1)  # Yield
        collect()
        await asyncio.sleep_ms(1)  # Yield

        # Emettre requete
        websocket.send(buffer.get_data())

    return offset_info


async def verifier_signature(reponse, buffer):
    return await verifier_message(reponse, buffer)


async def _traiter_commande(appareil, reponse, info_certificat):
    return await traiter_commande(appareil, reponse, info_certificat)


class PollingThread:

    def __init__(self, appareil, buffer, duree_thread):
        self.__appareil = appareil
        self.__timeout_http = 60
        self.__duree_thread = duree_thread

        self.__load_initial = True
        self.__prochain_refresh_config = 0
        self.__refresh_step = 0
        self.__url_relai = None
        self.__errnumber = 0
        
        self.__buffer = buffer
        self.__websocket = None
        
        self.__nie_count = 0

    async def preparer(self):
        self.__timeout_http = get_http_timeout()
        
    async def connecter(self):
        self.__load_initial = True
        self.__refresh_step = 0
        self.__errnumber = 0
        
        # Assigner un URL
        self.entretien_url_relai()
        
        print("PRE CONNECT")
        mem_info()

        url_connexion = self.__url_relai + '/ws'
        url_connexion = url_connexion.replace('https://', 'wss://')
        print("URL connexion websocket %s" % url_connexion)
        self.__websocket = connect(url_connexion)
        self.__websocket.setblocking(False)
        print("websocket connecte")
        mem_info()
        
    def entretien_url_relai(self):
        if self.__url_relai is None or self.__nie_count >= 3:
            self.__url_relai = self.__appareil.pop_relais()
            print("Utilisation relai %s" % self.__url_relai)
            self.__nie_count = 0  # Reset compte erreurs connexion

        if self.__url_relai is None:
            raise Exception('URL relai None')

    def _refresh_config(self):
        # Forcer un refresh de la liste de relais (via fiche MilleGrille)
        print("Refresh config %d" % self.__refresh_step)
        
        if self.__refresh_step <= 1:
            self.__refresh_step = 2
            # Recharger la configuration des displays
            await requete_configuration_displays(self.__websocket, buffer=self.__buffer)
            return

        if self.__refresh_step <= 2:
            self.__refresh_step = 3
            offset = await charger_timeinfo(
                self.__websocket,
                buffer=self.__buffer,
                refresh=not self.__load_initial)
            print("Set offset %s" % offset)
            # self.__appareil.set_timezone_offset(offset)
            return
        
        if self.__refresh_step <= 3:
            self.__refresh_step = 4
            # Verifier si le certificat doit etre renouvelle
            await verifier_renouveler_certificat_ws(self.__websocket, buffer=self.__buffer)
            return

        if self.__refresh_step <= 4:
            self.__refresh_step = 5
            # Verifier si le certificat doit etre renouvelle
            await requete_relais_web(self.__websocket, buffer=self.__buffer)
            return

        # Succes - ajuster prochain refresh
        self.__load_initial = False  # Complete load initial
        self.__prochain_refresh_config = CONST_EXPIRATION_CONFIG + time.time()
        self.__refresh_step = 0
        print("Refresh config complete")

    async def run(self):
        # Faire expirer la thread pour reloader la fiche/url, entretien certificat
        expiration_certificat, _pk = get_expiration_certificat_local()
        expiration_thread = min(time.time() + self.__duree_thread, expiration_certificat)
        
        print("Expiration thread %s (exp cert %s)" % (expiration_thread, expiration_certificat))

        while expiration_thread > time.time():
            try:
                print("Expiration thread dans %s " % (expiration_thread - time.time()))
                
                # Connecter
                try:
                    await self.connecter()
                except OSError as e:
                    if e.errno == 104:
                        # ECONNRESET
                        self.__nie_count += 1
                        await asyncio.sleep_ms(500)
                        continue  # Retry
                    elif e.errno == -2:
                        # Erreur connexion (e.g. refused)
                        self.__url_relai = None
                        self.entretien_url_relai()
                        continue
                    else:
                        raise e
                    
                # Boucle polling sur connexion websocket
                while expiration_thread > time.time():
                    print("Expiration thread dans %s " % (expiration_thread - time.time()))
                    
                    if time.time() > self.__prochain_refresh_config:
                        await self._refresh_config()
                        await asyncio.sleep_ms(1)
                        collect()
                        await asyncio.sleep_ms(1)

                    try:
                        await self._poll()
                        self.__nie_count = 0  # Reset erreurs
                    except NotImplementedError as e:
                        self.__nie_count += 1
                        print("Erreur websocket (NotImplementedError %s)" % str(e))
                        print_exception(e)
                        break  # Break inner loop
                    except OSError as e:
                        if e.errno == -104:
                            print("Connexion websocket fermee (serveur)")
                            self.__nie_count += 1
                            break  # Break inner loop
                        else:
                            # Erreur non geree, exit polling
                            raise e
            finally:
                print("Close websocket")
                mem_info()
                try:
                    self.__websocket.close()
                except AttributeError:
                    pass  # Websocket est None
                except OSError as e:
                    if e.errno == -104:
                        pass  # Erreur frame fermeture - OK
                    else:
                        raise e
                self.__websocket = None
                collect()
                print("Collect")
                mem_info()
                print("--- Socket closed --- ")
            
    async def _poll(self):
        try:
            reponse = await poll(
                self.__websocket,
                self.__buffer,
                self.__timeout_http,
                self.__appareil.get_etat,
                self.__appareil.ui_lock
            )
            
            await asyncio.sleep_ms(10)  # Yield

            if reponse is not None and len(reponse) > 0:
                # Remettre memoryview dans buffer - ajuste len
                self.__buffer.set_bytes(reponse)
                reponse = None

                # Cleanup memoire - tout est copie dans le buffer
                await asyncio.sleep_ms(20)  # Yield
                collect()
                await asyncio.sleep_ms(30)  # Yield

                try:
                    reponse = loads(self.__buffer.get_data())
                except ValueError:
                    len_buffer = len(self.__buffer.get_data())
                    print('*** JSON Decode error, len %d ***' % len_buffer)
                    #with open('err.txt', 'wb') as fichiers:
                    #    fichiers.write(self.__buffer.get_data()[:len_buffer])
                else:
                    await asyncio.sleep_ms(50)  # Yield
                    try:
                        len_buffer = len(self.__buffer.get_data())
                        info_certificat = await verifier_signature(reponse, self.__buffer)
                        print("Message websocket recu (valide, len %d)" % len_buffer)

                        # Cleanup
                        # info_certificat = None
                        await asyncio.sleep_ms(20)  # Yield
                
                        await _traiter_commande(self.__appareil, reponse, info_certificat)
                    except KeyError as e:
                        print("Erreur reception KeyError %s" % str(e))
                        print("ERR Message\n%s" % reponse)

            # Cleanup
            reponse = None
            await asyncio.sleep_ms(50)  # Yield
            collect()
            await asyncio.sleep_ms(50)  # Yield
            
            # Run polling completee, reset erreurs
            self.__errnumber = 0
            self.__appareil.reset_erreurs()
        
        # TODO Fix erreurs, detecter deconnexion websocket
        except HttpErrorException as e:
            raise e  # Retour pour recharger fiche/changer relai
