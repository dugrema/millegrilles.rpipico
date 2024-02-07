# Programme appareil millegrille
import json
import time
import machine
import os
import sys
import uasyncio as asyncio
import urequests

from gc import collect
from micropython import mem_info

from millegrilles import const_leds
from millegrilles import mgmessages
from millegrilles import wifi
from millegrilles.ledblink import led_executer_sequence

from millegrilles import feed_display

# from mgbluetooth import BluetoothHandler
from millegrilles.mgbluetooth import BluetoothHandler

from millegrilles.websocket_messages import PollingThread, CONST_DUREE_THREAD_POLLING
from handler_devices import DeviceHandler
from handler_programmes import ProgrammesHandler
from millegrilles.certificat import entretien_certificat as __entretien_certificat, PATH_CERT
from millegrilles.message_inscription import run_inscription, recuperer_ca, \
     verifier_renouveler_certificat as __verifier_renouveler_certificat, parse_url, charger_fiche
from millegrilles.chiffrage import ChiffrageMessages

from millegrilles.webutils import reboot

# from dev import config
from millegrilles.config import \
     set_time, detecter_mode_operation, get_tz_offset, initialisation, initialiser_wifi, get_relais, \
     get_timezone_transition, transition_timezone, sauvegarder_relais

from millegrilles.constantes import  CONST_MODE_INIT, CONST_MODE_RECUPERER_CA, CONST_MODE_CHARGER_URL_RELAIS, \
     CONST_MODE_SIGNER_CERTIFICAT, CONST_MODE_POLLING, CONST_PATH_FICHIER_DISPLAY

CONST_INFO_SEP = const(' ---- INFO ----')
CONST_NB_ERREURS_RESET = const(10)
CONST_HTTP_TIMEOUT_DEFAULT = const(60)
_CONST_INTERVALLE_REFRESH_FICHE = const(1 * 60 * 60)


# Initialiser classe de buffer
BUFFER_MESSAGE = mgmessages.BufferMessage(16*1024)


async def entretien_certificat():
    try:
        return await __entretien_certificat()
    except Exception as e:
        print("Erreur entretien certificat")
        sys.print_exception(e)
    
    return False


async def verifier_renouveler_certificat(url_relai: str):
    try:
        return await __verifier_renouveler_certificat(url_relai)
    except Exception as e:
        print("Erreur verif renouveler certificat")
        sys.print_exception(e)


class Runner:
    
    def __init__(self):
        self._mode_operation = 0
        self._device_handler = DeviceHandler(self)
        self._programmes_handler = ProgrammesHandler(self)
        self.task_runner = None  # TaskRunner()
        self._bluetooth_handler = BluetoothHandler(self)

        self._lectures_courantes = dict()
        self._lectures_externes = dict()
        self.__emit_event = asyncio.Event()    # Indique que l'etat a ete modifie, doit etre emis
        self.__stale_event = asyncio.Event()   # Indique que l'etat interne doit etre mis a jour
        self.__lectures_event = asyncio.Event()  # Utilise pour attendre une maj de lectures
        self.__rtc_pret = asyncio.Event()       # Indique que WIFI et l'heure interne (RTC) sont prets.
        self.__websocket_pret = asyncio.Event() # Indique que l'appareil est connecte et pret.
        self.__url_relais = None
        self.__ui_lock = None  # Lock pour evenements UI (led, ecrans)
        
        self.__wifi_ok = False
        # self.__ntp_ok = False
        self.__prochain_entretien_certificat = 0
        self.__prochain_refresh_fiche = 0
        self.__timezone_offset = None
        self.__erreurs_memory = 0  # Nombre de MemoryErrors depuis succes
        self.__erreurs_enomem = 0  # Nombre de Errno12 ENOMEM (ussl.wrap_socket) depuis succes
        self.__override_display = None
        self.__override_display_expiration = None
        self.__display_actif = False

        # Information de chiffrage
        self.__chiffrage_messages = ChiffrageMessages()

    def set_rtc_pret(self):
        if self.__rtc_pret.is_set() is not True:
            self.__rtc_pret.set()

    def set_websocket_pret(self):
        if self.__websocket_pret.is_set() is not True:
            self.__websocket_pret.set()

    def reset_websocket_pret(self):
        self.__websocket_pret.clear()

    @property
    def rtc_pret(self) -> asyncio.Event:
        return self.__rtc_pret

    @property
    def websocket_pret(self) -> asyncio.Event:
        return self.__websocket_pret

    @property
    def emit_event(self):
        return self.__emit_event
    
    @property
    def stale_event(self):
        return self.__stale_event

    def trigger_stale_event(self):
        self.__lectures_event.clear()
        self.__stale_event.set()

    async def trigger_emit_event(self):
        self.__emit_event.set()

    @property
    def chiffrage_messages(self) -> ChiffrageMessages:
        return self.__chiffrage_messages
    
    async def configurer_devices(self):
        self.__ui_lock = asyncio.Lock()
        await self._device_handler.load(self.__ui_lock)
    
    async def configurer_programmes(self):
        await self._programmes_handler.initialiser()
    
    def recevoir_lectures(self, lectures):
        self._lectures_courantes = lectures
        self.__lectures_event.set()

    def recevoir_lectures_externes(self, lectures: dict):
        # print("recevoir_lectures: %s" % lectures)
        self._lectures_externes.update(lectures)
        print("Lectures externes maj\n%s" % self._lectures_externes)
        
    @property
    def mode_operation(self):
        return self._mode_operation

    @property
    def lectures_courantes(self):
        return self._lectures_courantes
    
    @property
    def lectures_externes(self):
        return self._lectures_externes
    
    @property
    def timezone(self):
        if self.__rtc_pret.is_set() is not True:
            return None
        return get_tz_offset()
    
    @property
    def ui_lock(self):
        return self.__ui_lock
    
    @property
    def wifi_ok(self):
        return self.__rtc_pret.is_set()
    
    @property
    def display_actif(self):
        return self.__display_actif
    
    def get_device(self, device_id):
        print("Charger device %s" % device_id)
        devices = self._device_handler.devices
        print("List devices %s" % devices.keys())
        return self._device_handler.get_device(device_id)
    
    def reset_erreurs(self):
        self.__erreurs_memory = 0
        self.__erreurs_enomem = 0
    
    async def ajouter_programme(self, configuration: dict):
        await self._programmes_handler.ajouter_programme(configuration)
    
    async def supprimer_programme(self, programme_id: str):
        await self._programmes_handler.arreter_programme(programme_id)

    async def rafraichir_etat(self):
        liste_senseurs_programmes = set()
        try:
            # Extraire liste de senseurs utilises pour l'affichage
            for display in self.get_configuration_display().values():
                try:
                    for ligne in display['lignes']:
                        # print("Config appareils ligne : %s" % ligne)
                        try:
                            if ligne['variable'] is not None and len(ligne['variable'].split(':')) > 1:
                                liste_senseurs_programmes.add(ligne['variable'])
                        except KeyError:
                            pass  # Pas de variable configuree
                except KeyError:
                    pass  # Pas de lignes configurees
        except (OSError, AttributeError) as e:
            print("get_etat Error displays : %s" % e)
            # senseurs = None

        try:
            # Extraire liste de senseurs utilises par les programmes
            for senseur_id in self._programmes_handler.get_senseurs():
                try:
                    if len(senseur_id.split(':')) > 1:
                        liste_senseurs_programmes.add(senseur_id)
                except KeyError:
                    pass  # Pas un senseur externe

            liste_senseurs_programmes = list(liste_senseurs_programmes)
            print("Senseurs externes : %s" % liste_senseurs_programmes)
        except (OSError, AttributeError) as e:
            print("get_etat Error senseurs : %s" % e)

        if len(liste_senseurs_programmes) == 0:
            liste_senseurs_programmes = None

        try:
            await asyncio.wait_for(self.__lectures_event.wait(), 5)
        except TimeoutError:
            pass

        return liste_senseurs_programmes

    async def get_etat(self, refresh=True):
        # Clear evenement emit - les changements subsequents ne sont pas captures
        self.emit_event.clear()

        ticks_debut = time.ticks_ms()

        if refresh is True:
            liste_senseurs_programmes = await self.rafraichir_etat()
        else:
            print('get_etat Skip refresh')
            liste_senseurs_programmes = None

        etat = {
            'lectures_senseurs': self._lectures_courantes,
            'displays': self._device_handler.get_output_devices(),
            'senseurs': liste_senseurs_programmes,
        }

        try:
            notifications = await self._programmes_handler.get_notifications()
            if notifications is not None:
                etat['notifications'] = notifications
        except Exception as e:
            print("get_etat Error notifications : %s" % e)

        print("get_etat duree %d ms (refresh:%s)" % (time.ticks_diff(time.ticks_ms(), ticks_debut), refresh))

        return etat

    async def _signature_certificat(self):
        """
        Mode d'attente de signature de certificat
        """
        collect()

        certificat_recu = False
        while certificat_recu is False:
            try:
                os.stat(PATH_CERT)
                certificat_recu = True
                break  # Certificat existe
            except:
                pass  # Ok, certificat absent
            
            for url_relai in self.__url_relais:
                try:
                    print("Signature certificat avec relai %s " % url_relai)
                    await run_inscription(self, url_relai, self.__ui_lock, buffer=BUFFER_MESSAGE)
                    certificat_recu = True
                    break
                except OSError as ose:
                    if ose.errno == 12:
                        raise ose
                    else:
                        print("OS Error %s" % str(ose))
                        sys.print_exception(ose)
                except (AttributeError, IndexError):
                    print("Aucun url relais")
                except Exception as e:
                    print("Erreur chargement fiche %s" % e)
                finally:
                    collect()

            await asyncio.sleep(10)

        print("_signature_certificat Done")

    def feed_default(self):
        return feed_display.FeedDisplayDefault(self)

    def feed_custom(self, name, config):
        return feed_display.FeedDisplayCustom(self, name, config)

    def get_feeds(self, name=None):
        self.__display_actif = True
        if name is None:
            return self.feed_default()
        try:
            config_feed = self.get_configuration_display()[name]
            return self.feed_custom(name, config_feed)
        except (AttributeError, OSError, KeyError, TypeError):
            print("Feed %s inconnu, defaulting" % name)
            return self.feed_default()
    
    def set_display_override(self, override, duree=5):
        print("Set display override %s" % override)
        self.__override_display_expiration = time.time() + duree
        self.__override_display = override
        
    def get_display_override(self):
        if self.__override_display_expiration is not None:
            if self.__override_display_expiration < time.time():
                # Override est expire, on nettoie
                self.__override_display_expiration = None
            else:
                return self.__override_display
        self.__override_display = None
    
    async def entretien(self, init=False):
        """
        Thread d'entretien
        """
        while True:
            print("Entretien mode %d" % self._mode_operation)
            await self.__ui_lock.acquire()

            await self.__entretien_cycle()
            
            if init is True:
                # Premiere run a l'initialisation
                break

            if self.__rtc_pret.is_set() is not True:
                try:
                    await asyncio.wait_for(self.__rtc_pret.wait(), 3)
                except asyncio.TimeoutError:
                    pass
            else:
                # Verifier si on approche du changement d'heure (daylight savings)
                # Va bloquer si la transition est due dans moins de 3 minutes
                transition_faite = await self.transition_timezone()

                if transition_faite is False:
                    await asyncio.sleep(120)

    async def transition_timezone(self):
        try:
            transition_time, transition_offset = get_timezone_transition()
            transition_delta = transition_time - time.time()
            print('tz transition dans %d secs' % transition_delta)

            if transition_delta < 180:
                # On se met en mode d'attente de transition
                await asyncio.sleep(transition_delta)
                await transition_timezone()
                return True

        except:
            pass

        return False

    async def __entretien_cycle(self):
        try:
            if self._mode_operation >= 1:
                # Verifier etat wifi
                self.__wifi_ok = wifi.is_wifi_ok()

                if self.__wifi_ok is False:
                    self.__rtc_pret.clear()
                    print("Restart wifi")
                    ip = await initialiser_wifi()
                    if ip is not None:
                        self.__wifi_ok = True
                        print("Wifi OK : ", ip)
                    else:
                        print("Wifi echec")
                    ip = None

            if self.__wifi_ok is True:

                if self.__rtc_pret.is_set() is not True:
                    await set_time()
                    self.set_rtc_pret()
                    # self.__ntp_ok = True

                if self._mode_operation == CONST_MODE_POLLING:
                    await entretien_certificat()

        except Exception as e:
            print("Erreur entretien: %s" % e)
            sys.print_exception(e)
        finally:
            self.__ui_lock.release()

    async def charger_urls(self):
        collect()
        await asyncio.sleep(0)

        if self.__rtc_pret.is_set() is True:
            try:
                refresh = self.__prochain_refresh_fiche == 0 or self.__prochain_refresh_fiche <= time.time()
                collect()
                await asyncio.sleep(0)

                relais = get_relais()
                print('charger_urls pre-refresh %s' % relais)
                if refresh:
                    try:
                        fiche, certificat = await charger_fiche(buffer=BUFFER_MESSAGE)
                        if fiche is not None:
                            relais = sauvegarder_relais(fiche)
                            print('charger_url relais fiche sauvegardee %s' % relais)
                            await asyncio.sleep(0)
                    except Exception as e:
                        print("Erreur chargement fiche, utiliser relais connus : %s" % str(e))
                        sys.print_exception(e)

                print('charger_urls relais %s' % relais)
                self.set_relais(relais)

                if refresh is True:
                    self.__prochain_refresh_fiche = _CONST_INTERVALLE_REFRESH_FICHE + time.time()
            except Exception:
                print('charger_urls erreur')
                sys.print_exception(e)
        else:
            print('charger_urls rtc non pret')

    def get_configuration_display(self):
        try:
            with open(CONST_PATH_FICHIER_DISPLAY, 'rb') as fichier:
                return json.load(fichier)
        except OSError:
            pass  # Fichier absent

    def set_relais(self, relais: list):
        if relais is not None:
            self.__url_relais = relais
        print("URL relais : %s" % self.__url_relais)
        
    def pop_relais(self):
        return self.__url_relais.pop()
    
    async def _polling(self):
        """
        Main thread d'execution du polling/commandes
        """
        collect()

        if self.__url_relais is None or len(self.__url_relais) == 0:
            await self.charger_urls()

        if self.__url_relais is None or len(self.__url_relais) == 0:
            raise Exception("aucuns relais, abort poll")

        duree_thread = CONST_DUREE_THREAD_POLLING
        polling_thread = PollingThread(self, BUFFER_MESSAGE, duree_thread=duree_thread)
        await polling_thread.preparer()
        await polling_thread.run()

    async def __initialisation(self):
        await initialisation()
        
    async def __recuperer_ca(self):
        await recuperer_ca(buffer=BUFFER_MESSAGE)

    async def __main(self):
        self._mode_operation = await detecter_mode_operation()
        CONST_MODE_OPERATION_INTIAL = const("Mode operation initial %d")
        print(CONST_MODE_OPERATION_INTIAL % self._mode_operation)
        
        await led_executer_sequence(const_leds.CODE_MAIN_DEMARRAGE, executions=1, ui_lock=self.__ui_lock)
        while True:
            try:
                self._mode_operation = await detecter_mode_operation()
                CONST_MODE_OPERATION = const("Mode operation: %s")
                print(CONST_MODE_OPERATION % self._mode_operation)

                if self._mode_operation >= CONST_MODE_CHARGER_URL_RELAIS:
                    await self.charger_urls()

                # Cleanup memoire
                await asyncio.sleep(0)  # Yield
                collect()
                await asyncio.sleep(0)  # Yield

                if self._mode_operation == CONST_MODE_INIT:
                    await self.__initialisation()
                elif self.__rtc_pret.is_set() is False:
                    await led_executer_sequence(const_leds.CODE_WIFI_NON_CONNECTE, 1, self.__ui_lock)
                    try:
                        await asyncio.wait_for(self.__rtc_pret.wait(), 30)
                    except asyncio.TimeoutError:
                        pass
                    continue
                elif self._mode_operation == CONST_MODE_RECUPERER_CA:
                    await self.__recuperer_ca()
                elif self._mode_operation == CONST_MODE_SIGNER_CERTIFICAT:
                    await self._signature_certificat()
                    continue
                elif self._mode_operation == CONST_MODE_POLLING:
                    await self._polling()
                    continue
                else:
                    CONST_MODE_OPERATION_NON_SUPPORTE = const("Mode operation non supporte : %d")
                    print(CONST_MODE_OPERATION_NON_SUPPORTE % self._mode_operation)
                    await led_executer_sequence(const_leds.CODE_MAIN_OPERATION_INCONNUE, executions=None)

            except OSError as e:
                if e.errno == 12:
                    self.__erreurs_enomem += 1
                    if self.__erreurs_enomem >= CONST_NB_ERREURS_RESET:
                        CONST_ENOMEM_COUNT = const("ENOMEM count:%d, reset")
                        print(CONST_ENOMEM_COUNT % self.__erreurs_enomem)
                        await led_executer_sequence(
                            const_leds.CODE_ERREUR_MEMOIRE, executions=1, ui_lock=self.__ui_lock)
                        reboot(e)

                    CONST_ERREUR_MEMOIRE = const("Erreur memoire no %d")
                    print(CONST_ERREUR_MEMOIRE % self.__erreurs_enomem)
                    sys.print_exception(e)
                    collect()
                    self.afficher_info()
                    await asyncio.sleep_ms(500)
                    continue

                else:
                    CONST_OSERROR_MAIN = const("OSError main")
                    print(CONST_OSERROR_MAIN)
                    sys.print_exception(e)
                    collect()
                    self.afficher_info()
                    self.__prochain_refresh_fiche = time.time()  # Forcer refresh de la fiche
                    await asyncio.sleep(20)

            except MemoryError as e:
                self.__erreurs_memory += 1
                if self.__erreurs_memory >= CONST_NB_ERREURS_RESET:
                    CONST_MEMORYERROR1 = const("MemoryError count:%d, reset")
                    print(CONST_MEMORYERROR1 % self.__erreurs_memory)
                    reboot(e)

                CONST_MEMORYERROR2 = const("MemoryError %s")
                print(CONST_MEMORYERROR2 % e)
                sys.print_exception(e)
                CONST_MEMORYERROR3 = const("Erreur memoire no %d\n%s")
                print(CONST_MEMORYERROR3 % (self.__erreurs_memory, mem_info()))
                collect()
                self.afficher_info()
                await asyncio.sleep_ms(50)
            except Exception as e:
                CONST_ERREUR_MAIN = const("Erreur main")
                print(CONST_ERREUR_MAIN)
                collect()
                sys.print_exception(e)
                self.afficher_info()
                self.__prochain_refresh_fiche = time.time()  # Forcer refresh de la fiche

            # Erreur execution ou changement runlevel
            await led_executer_sequence(const_leds.CODE_MAIN_ERREUR_GENERALE, 2, self.__ui_lock)
    
    async def run(self):
        self.afficher_info()
        
        # Charger configuration
        await self.configurer_devices()
        
        await self.configurer_programmes()

        # Demarrer thread entretien (wifi, date, configuration)
        await self.entretien(init=True)
        entretien_task = asyncio.create_task(self.entretien())

        # Task devices
        devices_task = asyncio.create_task(self._device_handler.run(
            self.__ui_lock, self.recevoir_lectures, self.get_feeds, 20_000))

        # Task bluetooth
        bluetooth_task = asyncio.create_task(self._bluetooth_handler.run())

        # Executer main loop
        main_task = asyncio.create_task(self.__main())

        err = None
        try:
            await asyncio.gather(entretien_task, devices_task, bluetooth_task, main_task)
        except Exception as e:
            err = e
            sys.print_exception(e)
            CONST_ERREUR1 = const("Erreur main(), reboot dans 30 secondes")
            print(CONST_ERREUR1)
        else:
            CONST_ERREUR2 = const("main() arrete, reboot dans 30 secondes")
            print(CONST_ERREUR2)

        await asyncio.sleep(30)
        reboot(err)

    def afficher_info(self):
        CONST_HEURE = const("Heure %s")
        CONST_CPU = const("CPU freq %d")
        CONST_MEMOIRE = const("Memoire")
        print(CONST_INFO_SEP)
        print(CONST_HEURE % str(time.gmtime()))
        print(CONST_CPU % machine.freq())
        print(CONST_MEMOIRE)
        mem_info()
        print(CONST_INFO_SEP + '\n')


async def main():
    machine.freq(133000000)
    runner = Runner()
    await runner.run()


if __name__ == '__main__':
    asyncio.run(main())
