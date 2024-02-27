import time
import uasyncio as asyncio

from binascii import hexlify
from json import dumps, loads, load, dump
from gc import collect
from sys import print_exception
from micropython import mem_info

from uwebsockets.client import connect
from millegrilles.certificat import get_expiration_certificat_local
from millegrilles.mgmessages import formatter_message, verifier_message
from millegrilles.config import get_http_timeout, set_configuration_display, get_timezone, set_timezone_offset, CONST_PATH_TZOFFSET, get_tz_offset

from millegrilles.message_inscription import verifier_renouveler_certificat_ws, generer_message_timeinfo

# Import dev/prod
# from handler_commandes import traiter_commande
from millegrilles.handler_commandes import traiter_commande


PATHNAME_POLL = const('/poll')
PATHNAME_REQUETE = const('/requete')
CONST_CHAMP_TIMEOUT = const('http_timeout')

CONST_DOMAINE_SENSEURSPASSIFS = const('SenseursPassifs')
CONST_DOMAINE_SENSEURSPASSIFS_RELAI = const('senseurspassifs_relai')
CONST_REQUETE_DISPLAY = const('getAppareilDisplayConfiguration')
CONST_REQUETE_PROGRAMMES = const('getAppareilProgrammesConfiguration')
CONST_REQUETE_FICHE_PUBLIQUE = const('getFichePublique')
CONST_REQUETE_RELAIS_WEB = const('getRelaisWeb')
CONST_COMMANDE_ECHANGE_CLES = const('echangerClesChiffrage')

# Durees en secondes
CONST_EXPIRATION_CONFIG = const(8 * 3600)


class HttpErrorException(Exception):
    pass


async def __preparer_message(chiffrage_messages, timeout_http, generer_etat, buffer, refresh=True):
    # Genrer etat
    if generer_etat is not None:
        etat = await generer_etat(refresh=refresh)
    else:
        etat = {'lectures_senseurs': {}}
        
    # Ajouter timeout pour limite polling
    etat[CONST_CHAMP_TIMEOUT] = timeout_http

    if chiffrage_messages.pret is True:
        # Chiffrer le message
        print('preparer_message chiffrer')
        etat = await chiffrage_messages.chiffrer(etat)
        etat['routage'] = {'action': 'etatAppareilRelai'}
    else:
        # Signer message
        etat = await formatter_message(etat, kind=2, domaine=CONST_DOMAINE_SENSEURSPASSIFS, action='etatAppareil', buffer=buffer)

    buffer.clear()
    dump(etat, buffer)

    return buffer


async def poll(appareil, websocket, emit_event, buffer, timeout_http=60, generer_etat=None):
    # Calculer limite de la periode de polling
    if timeout_http is None or timeout_http < 1:
        timeout_http = 1  # Min pour executer entretien websocket

    expiration_polling = time.time() + timeout_http
    print("expiration polling dans %s" % timeout_http)

    # Poll socket
    cycle = 0
    deja_emis = False
    emettre = False
    refresh = True

    while expiration_polling > time.time():
        cycle += 1
        
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

        if cycle > 3 and emit_event.is_set():
            print("Emit event set, emettre")
            emettre = True
            refresh = False
        elif cycle == 30 and deja_emis is False:
            emettre = True
        else:
            # Intervalle polling socket
            await asyncio.sleep_ms(100)

        if emettre is True:
            emettre = False
            deja_emis = True
            chiffrage_messages = appareil.chiffrage_messages
            buffer = await __preparer_message(chiffrage_messages, timeout_http, generer_etat, buffer, refresh=refresh)
            print("poll Send data, taille etat: %d" % len(buffer))
            websocket.send(buffer.get_data())
            await asyncio.sleep_ms(1)  # Yield


async def requete_configuration_displays(chiffrage_messages, websocket, buffer):
    #requete = await signer_message(
    #    dict(), domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_DISPLAY)
    message = dict()

    # if chiffrage_messages.pret is True:
    #     # Chiffrer le message
    #     requete = await chiffrage_messages.chiffrer(message)
    #     requete['routage'] = {'action': CONST_REQUETE_DISPLAY}
    # else:
    requete = await formatter_message(message, kind=1,
                                      domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_DISPLAY,
                                      buffer=buffer, ajouter_certificat=True)
    buffer.set_text(dumps(requete))
    requete = None

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    print('requete_configuration_displays')
    websocket.send(buffer.get_data())


async def requete_configuration_programmes(chiffrage_messages, websocket, buffer):
    #requete = await signer_message(
    #    dict(), domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_PROGRAMMES)
    requete = await formatter_message(dict(), kind=1,
                                      domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_PROGRAMMES,
                                      buffer=buffer, ajouter_certificat=True)
    buffer.set_text(dumps(requete))
    requete = None

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    print('requete_configuration_programmes')
    websocket.send(buffer.get_data())


async def requete_fiche_publique(websocket, buffer):
    #requete = await signer_message(
    #    dict(), domaine='senseurspassifs_relai', action=CONST_REQUETE_FICHE_PUBLIQUE)
    requete = await formatter_message(dict(), kind=1,
                                      domaine=CONST_DOMAINE_SENSEURSPASSIFS_RELAI, action=CONST_REQUETE_FICHE_PUBLIQUE,
                                      buffer=buffer, ajouter_certificat=True)
    buffer.set_text(dumps(requete))
    requete = None

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    websocket.send(buffer.get_data())


async def requete_relais_web(chiffrage_messages, websocket, buffer):
    #requete = await signer_message(
    #    dict(), domaine=CONST_DOMAINE_SENSEURSPASSIFS_RELAI, action=CONST_REQUETE_RELAIS_WEB, buffer=buffer)

    if chiffrage_messages.pret is True:
        # Chiffrer le message
        requete = await chiffrage_messages.chiffrer(dict())
        requete['routage'] = {'action': CONST_REQUETE_RELAIS_WEB}
    else:
        requete = await formatter_message(dict(), kind=1,
                                          domaine=CONST_DOMAINE_SENSEURSPASSIFS_RELAI, action=CONST_REQUETE_RELAIS_WEB,
                                          buffer=buffer, ajouter_certificat=True)
    buffer.clear()
    dump(requete, buffer)
    requete = None

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    websocket.send(buffer.get_data())


async def charger_timeinfo(chiffrage_messages, websocket, buffer, refresh: False):

    offset = None
    try:
        offset = get_tz_offset()
        if refresh is False:
            return offset
    except OSError:
        print('tzoffset.json absent')
    except KeyError:
        print('tzoffset.json erreur contenu')

    timezone_str = get_timezone()
    if offset is None and timezone_str is None:
        timezone_str = None
        # Generer fichier dummy
        set_timezone_offset(0, timezone='UTC')

    latitude = None
    longitude = None
    try:
        with open('geoposition.json', 'rb') as fichier:
            geoposition = load(fichier)
        latitude = geoposition['latitude']
        longitude = geoposition['longitude']
    except OSError:
        print('geoposition.json absent')
    except KeyError:
        print('geoposition.json erreur contenu')

    print("Charger information timezone %s" % timezone_str)

    if chiffrage_messages.pret is True:
        # Chiffrer le message
        requete = {'timezone': timezone_str}
        if latitude and longitude:
            requete['latitude'] = latitude
            requete['longitude'] = longitude
        requete = await chiffrage_messages.chiffrer(requete)
        requete['routage'] = {'action': 'getTimezoneInfo'}
    else:
        requete = await generer_message_timeinfo(timezone_str)

    buffer.set_text(dumps(requete))

    await asyncio.sleep_ms(1)  # Yield
    collect()
    await asyncio.sleep_ms(1)  # Yield

    # Emettre requete
    websocket.send(buffer.get_data())


async def verifier_signature(reponse, buffer):
    return await verifier_message(reponse, buffer)


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
        self.__memory_error = 0

    @property
    def emit_event(self):
        return self.__appareil.emit_event

    async def preparer(self):
        self.__timeout_http = get_http_timeout()
        
    async def connecter(self):
        self.__load_initial = True
        self.__refresh_step = 0
        self.__errnumber = 0

        # Assigner un URL
        self.entretien_url_relai()

        chiffrage_messages = self.__appareil.chiffrage_messages
        chiffrage_messages.clear()
        self.__prochain_refresh_config = 0  # Forcer recharger config sur connexion. Permet aussi chiffrage.

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

        chiffrage_messages = self.__appareil.chiffrage_messages

        if self.__refresh_step <= 1:
            self.__refresh_step = 2
            await self.echanger_secret()
            return

        if self.__refresh_step <= 2:
            self.__refresh_step = 3
            # Recharger la configuration des displays
            await requete_configuration_displays(chiffrage_messages, self.__websocket, buffer=self.__buffer)
            return

        if self.__refresh_step <= 3:
            self.__refresh_step = 4
            await charger_timeinfo(
                chiffrage_messages,
                self.__websocket,
                buffer=self.__buffer,
                refresh=True)
            return
        
        if self.__refresh_step <= 4:
            self.__refresh_step = 5
            # Recharger la configuration des programmes
            await requete_configuration_programmes(chiffrage_messages, self.__websocket, buffer=self.__buffer)
            return
        
        if self.__refresh_step <= 5:
            self.__refresh_step = 6
            # Verifier si le certificat doit etre renouvelle
            await verifier_renouveler_certificat_ws(self.__websocket, buffer=self.__buffer)
            return

        if self.__refresh_step <= 6:
            self.__refresh_step = 7
            # Verifier si le certificat doit etre renouvelle
            await requete_relais_web(chiffrage_messages, self.__websocket, buffer=self.__buffer)
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

        self.__appareil.set_websocket_pret()
        while expiration_thread > time.time() and self.__memory_error < 10:
            try:
                print("Expiration thread dans %s " % (expiration_thread - time.time()))
                
                # Connecter
                try:
                    await self.connecter()
                except AssertionError:
                    # Erreur connexion (e.g. status code 502)
                    self.__url_relai = None
                    self.entretien_url_relai()
                    continue
                except OSError as e:
                    if e.errno == 104:
                        # ECONNRESET
                        self.__nie_count += 1
                        await asyncio.sleep_ms(500)
                        continue  # Retry
                    elif e.errno in (103, -2):
                        # Erreur connexion (e.g. ECONNABORTED, refused)
                        self.__url_relai = None
                        self.entretien_url_relai()
                        continue
                    else:
                        raise e
                    
                # Boucle polling sur connexion websocket
                while expiration_thread > time.time() and self.__memory_error < 10:
                    print("Expiration thread dans %s " % (expiration_thread - time.time()))

                    if time.time() > self.__prochain_refresh_config:
                        await self._refresh_config()
                        await asyncio.sleep_ms(1)
                        collect()
                        await asyncio.sleep_ms(1)

                    try:
                        print("debut ws poll")
                        await self._poll()
                        print("fin ws poll OK")
                        # Reset erreurs
                        self.__nie_count = 0
                        self.__memory_error = 0
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
                        elif e.errno == 12:
                            self.__memory_error += 1
                            collect()
                        else:
                            # Erreur non geree, exit polling
                            raise e
                    except MemoryError as e:
                        self.__memory_error += 1
                        collect()

            finally:
                self.__appareil.reset_websocket_pret()
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
                self.__appareil,
                self.__websocket,
                self.emit_event,
                self.__buffer,
                self.__timeout_http,
                self.__appareil.get_etat,
            )
            
            await asyncio.sleep_ms(1)  # Yield

            if reponse is not None and len(reponse) > 0:
                # Remettre memoryview dans buffer - ajuste len
                self.__buffer.set_bytes(reponse)
                reponse = None

                # Cleanup memoire - tout est copie dans le buffer
                await asyncio.sleep_ms(1)  # Yield
                collect()
                await asyncio.sleep_ms(3)  # Yield

                try:
                    reponse = loads(self.__buffer.get_data())
                except ValueError:
                    len_buffer = len(self.__buffer.get_data())
                    print('*** JSON Decode error, len %d ***' % len_buffer)
                    #with open('err.txt', 'wb') as fichiers:
                    #    fichiers.write(self.__buffer.get_data()[:len_buffer])
                else:
                    await asyncio.sleep_ms(5)  # Yield
                    len_buffer = len(self.__buffer.get_data())
                    print("Message websocket recu (len %d)" % len_buffer)
                    try:
                        try:
                            routage = reponse['routage']
                            message_chiffre = reponse['attachements']['relai_chiffre']

                            # Dechiffrer le message
                            try:
                                reponse = self.__appareil.chiffrage_messages.dechiffrer(message_chiffre)
                            except Exception as e:
                                print('err Desactiver chiffrage : %s' % e)
                                self.__appareil.chiffrage_messages.clear()
                                raise e  # Fallback sur message signe

                            print("message websocket dechiffre OK")
                            # Le message dechiffre est en bytes, charger avec json
                            reponse = loads(reponse)

                            # On peut se fier au message dechiffre sans valider le reste du contenu
                            info_certificat = reponse['enveloppe']
                            reponse = {'routage': routage, 'contenu': reponse['contenu']}
                        except Exception:
                            # On n'a pas de message chiffre ou echec dechiffrage. Valider le message au complet.
                            info_certificat = await verifier_signature(reponse, self.__buffer)

                        # Cleanup
                        await asyncio.sleep_ms(2)  # Yield

                        await traiter_commande(self.__buffer, self.__websocket, self.__appareil, reponse, info_certificat)
                    except KeyError as e:
                        print("Erreur reception KeyError %s" % str(e))
                        print("ERR Message\n%s" % reponse)

            # Cleanup
            reponse = None
            # await asyncio.sleep_ms(5)  # Yield
            # collect()
            await asyncio.sleep_ms(5)  # Yield
            
            # Run polling completee, reset erreurs
            self.__errnumber = 0
            self.__appareil.reset_erreurs()
        
        # TODO Fix erreurs, detecter deconnexion websocket
        except HttpErrorException as e:
            raise e  # Retour pour recharger fiche/changer relai

    async def echanger_secret(self):
        """ Genere une cle publique ed25519 pour obtenir un secret avec le serveur """
        from millegrilles.version import MILLEGRILLES_VERSION as CONST_VERSION

        chiffrage_messages = self.__appareil.chiffrage_messages
        if chiffrage_messages.doit_renouveler_secret() is False:
            return

        cle_publique = chiffrage_messages.generer_cle()
        message = {'peer': cle_publique, 'version': CONST_VERSION}

        print('echanger_secret public %s' % message)

        requete = await formatter_message(message, kind=2,
                                          domaine=CONST_DOMAINE_SENSEURSPASSIFS_RELAI,
                                          action=CONST_COMMANDE_ECHANGE_CLES,
                                          buffer=self.__buffer, ajouter_certificat=True)
        self.__buffer.clear()
        dump(requete, self.__buffer)
        requete = None
        await asyncio.sleep_ms(1)  # Yield

        self.__websocket.send(self.__buffer.get_data())
