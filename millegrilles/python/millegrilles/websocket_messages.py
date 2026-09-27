import _thread
import time
import uasyncio as asyncio

from json import dumps, loads, load
from gc import collect
from sys import print_exception

from micropython import mem_info, const
from millegrilles.mgthreads import dump_spawn

from uwebsockets.client import connect
from millegrilles.certificat import get_expiration_certificat_local
from millegrilles.config import get_http_timeout, get_timezone, set_timezone_offset, get_tz_offset

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


async def __preparer_message(cryptographie, watchdog, chiffrage_messages, timeout_http, generer_etat, buffer, refresh=True):
    # Genrer etat
    if generer_etat is not None:
        ticks_debut = time.ticks_ms()
        watchdog.feed()
        etat = await generer_etat(refresh=refresh)
        watchdog.feed()
        print("preparer_message etat duree ", end="")
        print(time.ticks_diff(time.ticks_ms(), ticks_debut))
    else:
        etat = {'lectures_senseurs': {}}
        
    # Ajouter timeout pour limite polling
    etat[CONST_CHAMP_TIMEOUT] = timeout_http

    if chiffrage_messages.pret is True:
        # Chiffrer le message
        print('preparer_message chiffrer')
        watchdog.feed()
        etat = await chiffrage_messages.chiffrer(etat)
        watchdog.feed()
        etat['routage'] = {'action': 'etatAppareilRelai'}
    else:
        # Signer message
        etat = await cryptographie.formatter_message(etat, kind=2, domaine=CONST_DOMAINE_SENSEURSPASSIFS, action='etatAppareil', buffer=buffer)

    ticks_debut = time.ticks_ms()
    watchdog.feed()
    buffer.clear()
    #watchdog.feed()
    # dump(etat, buffer)
    # print("dump_spawn etat")
    # print(etat)
    await dump_spawn(watchdog, etat, buffer)
    #watchdog.feed()
    print("preparer_message dump duree ", end="")
    print(time.ticks_diff(time.ticks_ms(), ticks_debut))

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

        if cycle > 5 and emit_event.is_set():
            print("Emit event set, emettre")
            emettre = True
            refresh = False
        elif cycle == 50 and deja_emis is False:
            emettre = True
        else:
            # Intervalle polling socket
            # await asyncio.sleep_ms(50)
            await appareil.watchdog.yield_duration(50)

        if emettre is True:
            print("Emettre")
            emettre = False
            deja_emis = True
            chiffrage_messages = appareil.chiffrage_messages
            appareil.watchdog.feed()
            buffer = await __preparer_message(appareil.cryptographie, appareil.watchdog, chiffrage_messages, timeout_http, generer_etat, buffer, refresh=refresh)
            appareil.watchdog.feed()
            print("poll Send data, taille etat: %d" % len(buffer))
            websocket.send(buffer.get_data())
            # await asyncio.sleep_ms(1)  # Yield
            await appareil.watchdog.yield_duration(1)


async def requete_configuration_displays(cryptographie, watchdog, chiffrage_messages, websocket, buffer):
    #requete = await signer_message(
    #    dict(), domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_DISPLAY)
    message = dict()

    requete = await cryptographie.formatter_message(message, kind=1,
                                      domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_DISPLAY,
                                      buffer=buffer, ajouter_certificat=True)
    buffer.set_text(dumps(requete))

    # Cleanup memoire
    await asyncio.sleep_ms(1)
    collect()
    await asyncio.sleep_ms(1)
    
    print('requete_configuration_displays')
    websocket.send(buffer.get_data())


async def requete_configuration_programmes(cryptographie, watchdog, chiffrage_messages, websocket, buffer):
    requete = await cryptographie.formatter_message(dict(), kind=1,
                                      domaine=CONST_DOMAINE_SENSEURSPASSIFS, action=CONST_REQUETE_PROGRAMMES,
                                      buffer=buffer, ajouter_certificat=True)
    buffer.set_text(dumps(requete))
    requete = None

    # Cleanup memoire
    await watchdog.yield_duration(1)
    collect()
    await watchdog.yield_duration(1)
    
    print('requete_configuration_programmes')
    websocket.send(buffer.get_data())


async def requete_relais_web(cryptographie, watchdog, chiffrage_messages, websocket, buffer):
    #requete = await signer_message(
    #    dict(), domaine=CONST_DOMAINE_SENSEURSPASSIFS_RELAI, action=CONST_REQUETE_RELAIS_WEB, buffer=buffer)

    watchdog.feed()
    print('Requete relais web')
    if chiffrage_messages.pret is True:
        # Chiffrer le message
        print('req chiffree')
        requete = await chiffrage_messages.chiffrer({'ok': True})  # Note: sending empty dict was causing issues after micropython 1.29
        watchdog.feed()
        requete['routage'] = {'action': CONST_REQUETE_RELAIS_WEB}
    else:
        print('req signee')
        requete = await cryptographie.formatter_message(dict(), kind=1,
                                          domaine=CONST_DOMAINE_SENSEURSPASSIFS_RELAI, action=CONST_REQUETE_RELAIS_WEB,
                                          buffer=buffer, ajouter_certificat=True)
    print('Requete prep done')
    await watchdog.yield_duration(1)
    buffer.clear()
    watchdog.feed()
    # dump(requete, buffer)
    print("Req to buf")
    await dump_spawn(watchdog, requete, buffer)
    watchdog.feed()
    requete = None

    # Cleanup memoire
    print("collect")
    await watchdog.yield_duration(1)
    collect()
    await watchdog.yield_duration(1)

    print("Sent requete relais web")
    websocket.send(buffer.get_data())


async def charger_timeinfo(cryptographie, watchdog, chiffrage_messages, websocket, buffer, refresh: False):

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
        requete = await generer_message_timeinfo(cryptographie, watchdog, timezone_str)

    buffer.set_text(dumps(requete))

    await asyncio.sleep_ms(1)  # Yield
    collect()
    await asyncio.sleep_ms(1)  # Yield

    # Emettre requete
    websocket.send(buffer.get_data())


async def verifier_signature(cryptographie, watchdog, reponse, buffer):
    return await cryptographie.verifier_message(reponse, buffer)


class PollingThread:

    def __init__(self, appareil, buffer, duree_thread):
        self.__appareil = appareil          # appareil_millegrille.Appareil
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
        self.__last_message_ts = time.time()

    @property
    def emit_event(self):
        return self.__appareil.emit_event

    async def preparer(self):
        self.__timeout_http = get_http_timeout()
        
    async def connecter(self):
        global ws_connection, ws_error, stop_feeding
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
        async with self.__appareil.watchdog:
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

    async def _refresh_config(self):
        # Forcer un refresh de la liste de relais (via fiche MilleGrille)
        print("Refresh config %d" % self.__refresh_step)

        watchdog = self.__appareil.watchdog
        chiffrage_messages = self.__appareil.chiffrage_messages

        # Refresh secret for message encryption
        if self.__refresh_step <= 1 and chiffrage_messages.doit_renouveler_secret:
            self.__refresh_step = 2
            await self.echanger_secret()
            return

        if self.__refresh_step <= 2:
            self.__refresh_step = 3
            # Recharger la configuration des displays
            await requete_configuration_displays(self.__appareil.cryptographie, watchdog, chiffrage_messages, self.__websocket, buffer=self.__buffer)
            return

        if self.__refresh_step <= 3:
            self.__refresh_step = 4
            await charger_timeinfo(
                self.__appareil.cryptographie,
                watchdog,
                chiffrage_messages,
                self.__websocket,
                buffer=self.__buffer,
                refresh=True
            )
            return
        
        if self.__refresh_step <= 4:
            self.__refresh_step = 5
            # Recharger la configuration des programmes
            await requete_configuration_programmes(self.__appareil.cryptographie, watchdog, chiffrage_messages, self.__websocket, buffer=self.__buffer)
            return
        
        if self.__refresh_step <= 5:
            self.__refresh_step = 6
            # Verifier si le certificat doit etre renouvelle
            await verifier_renouveler_certificat_ws(self.__appareil.cryptographie, watchdog, self.__websocket, buffer=self.__buffer)
            return

        if self.__refresh_step <= 6:
            self.__refresh_step = 7
            # Verifier si le certificat doit etre renouvelle
            await requete_relais_web(self.__appareil.cryptographie, watchdog, chiffrage_messages, self.__websocket, buffer=self.__buffer)
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
        was_connected = False
        while expiration_thread > time.time() and self.__memory_error < 10:
            await self.__appareil.watchdog.yield_duration(1)
            try:
                print("Expiration thread dans %s " % (expiration_thread - time.time()))
                
                # Connecter
                try:
                    await self.connecter()
                    was_connected = True
                    self.__appareil.set_websocket_connected()
                except AssertionError:
                    # Erreur connexion (e.g. status code 502)
                    self.__url_relai = None
                    self.entretien_url_relai()
                    await self.__appareil.watchdog.yield_duration(1)
                    continue
                except OSError as e:
                    if e.errno == 104:
                        # ECONNRESET
                        self.__nie_count += 1
                        # await asyncio.sleep_ms(500)
                        await self.__appareil.watchdog.yield_duration(500)
                        continue  # Retry
                    elif e.errno in (103, -2):
                        # Erreur connexion (e.g. ECONNABORTED, refused)
                        self.__url_relai = None
                        self.entretien_url_relai()
                        continue
                    else:
                        raise e
                finally:
                    await self.__appareil.watchdog.yield_duration(1)
                    
                # Boucle polling sur connexion websocket
                now = time.time()
                while expiration_thread > now and self.__memory_error < 10:
                    await self.__appareil.watchdog.yield_duration(1)
                    print("Expiration thread dans %s " % (expiration_thread - now))

                    if now > self.__prochain_refresh_config:
                        await self._refresh_config()
                        # await asyncio.sleep_ms(1)
                        await self.__appareil.watchdog.yield_duration(1)
                        collect()
                        await self.__appareil.watchdog.yield_duration(1)
                    elif self.__last_message_ts < now - (CONST_EXPIRATION_CONFIG+300):
                        # This is an attempt to force a reboot if the connection is not working properly
                        raise Exception(const('WS thread message timeout'))

                    try:
                        print(const("debut ws poll"))
                        self.__appareil.watchdog.feed()
                        await self._poll()
                        self.__appareil.watchdog.feed()
                        print(const("fin ws poll OK"))
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
                            print(const("Connexion websocket fermee (serveur)"))
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
                        self.__appareil.watchdog.feed()

                    # Update now
                    now = time.time()

            finally:
                self.__appareil.watchdog.feed()
                self.__appareil.reset_websocket_pret(was_connected)
                print(const("Close websocket"))
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
                print(const("Collect"))
                mem_info()
                print(const("--- Socket closed --- "))
            
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
            
            # await asyncio.sleep_ms(1)  # Yield
            await self.__appareil.watchdog.yield_duration(1)

            if reponse is not None and len(reponse) > 0:
                # Remettre memoryview dans buffer - ajuste len
                print("Response len ", end="")
                print(len(reponse))
                await self.__appareil.watchdog.yield_duration(1)
                self.__buffer.set_bytes(reponse)
                reponse = None

                # Cleanup memoire - tout est copie dans le buffer
                # await asyncio.sleep_ms(1)  # Yield
                await self.__appareil.watchdog.yield_duration(1)
                collect()
                # await asyncio.sleep_ms(3)  # Yield
                await self.__appareil.watchdog.yield_duration(1)

                try:
                    reponse = loads(self.__buffer.get_data())
                    self.__appareil.watchdog.feed()
                    if reponse:
                        # Keep track of messages - proxy to identify problems with the app server/connection
                        self.__last_message_ts = time.time()
                except ValueError:
                    len_buffer = len(self.__buffer.get_data())
                    print('*** JSON Decode error, len %d ***' % len_buffer)
                    #with open('err.txt', 'wb') as fichiers:
                    #    fichiers.write(self.__buffer.get_data()[:len_buffer])
                else:
                    # await asyncio.sleep_ms(5)  # Yield
                    await self.__appareil.watchdog.yield_duration(5)
                    len_buffer = len(self.__buffer.get_data())
                    print("Message websocket recu (len %d)" % len_buffer)
                    try:
                        try:
                            routage = reponse['routage']
                            message_chiffre = reponse['attachements']['relai_chiffre']

                            # Dechiffrer le message
                            try:
                                await self.__appareil.watchdog.yield_duration(1)
                                reponse = self.__appareil.chiffrage_messages.dechiffrer(message_chiffre)
                                self.__appareil.watchdog.feed()
                            except Exception as e:
                                print('err Desactiver chiffrage : %s' % e)
                                self.__appareil.chiffrage_messages.clear()
                                raise e  # Fallback sur message signe
                            finally:
                                await self.__appareil.watchdog.yield_duration(1)

                            print("message websocket dechiffre OK")
                            # Le message dechiffre est en bytes, charger avec json
                            reponse = loads(reponse)
                            self.__appareil.watchdog.feed()

                            # On peut se fier au message dechiffre sans valider le reste du contenu
                            info_certificat = reponse['enveloppe']
                            reponse = {'routage': routage, 'contenu': reponse['contenu']}
                        except Exception:
                            # On n'a pas de message chiffre ou echec dechiffrage. Valider le message au complet.
                            self.__appareil.watchdog.feed()
                            info_certificat = await verifier_signature(self.__appareil.cryptographie, self.__appareil.watchdog, reponse, self.__buffer)

                        # Cleanup
                        # await asyncio.sleep_ms(2)  # Yield
                        await self.__appareil.watchdog.yield_duration(2)

                        await traiter_commande(self.__buffer, self.__websocket, self.__appareil, reponse, info_certificat)
                        self.__appareil.watchdog.feed()
                    except KeyError as e:
                        print("Erreur reception KeyError %s" % str(e))
                        print("ERR Message\n%s" % reponse)

            # Cleanup
            reponse = None
            await self.__appareil.watchdog.yield_duration(5)
            
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

        watchdog = self.__appareil.watchdog
        watchdog.feed()
        cle_publique = chiffrage_messages.generer_cle()
        await watchdog.yield_duration(1)
        message = {'peer': cle_publique, 'version': CONST_VERSION}

        print('echanger_secret public %s' % message)

        requete = await self.__appareil.cryptographie.formatter_message(message, kind=2,
                                          domaine=CONST_DOMAINE_SENSEURSPASSIFS_RELAI,
                                          action=CONST_COMMANDE_ECHANGE_CLES,
                                          buffer=self.__buffer, ajouter_certificat=True)
        watchdog.feed()
        self.__buffer.clear()
        #dump(requete, self.__buffer)
        await dump_spawn(watchdog, requete, self.__buffer)
        requete = None
        await watchdog.yield_duration(1)

        self.__websocket.send(self.__buffer.get_data())
