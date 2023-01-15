# Programme appareil millegrille
import json
import time
import machine
import micropython
import sys
import uasyncio as asyncio

from ntptime import settime
from gc import collect
from micropython import mem_info

from millegrilles import const_leds
from millegrilles.const_leds import CODE_POLLING_ERREUR_GENERALE
from millegrilles import mgmessages
from millegrilles import wifi
from millegrilles.ledblink import led_executer_sequence

import feed_display
import config
from websocket_messages import PollingThread
from handler_devices import DeviceHandler
from millegrilles.certificat import entretien_certificat as __entretien_certificat, PATH_CERT
from message_inscription import run_inscription, \
     verifier_renouveler_certificat as __verifier_renouveler_certificat

from config import \
     CONST_MODE_INIT, \
     CONST_MODE_RECUPERER_CA, \
     CONST_MODE_CHARGER_URL_RELAIS, \
     CONST_MODE_SIGNER_CERTIFICAT, \
     CONST_MODE_POLLING, \
     detecter_mode_operation

from websocket_messages import CONST_DUREE_THREAD_POLLING

CONST_INFO_SEP = const(' ---- INFO ----')
CONST_NB_ERREURS_RESET = const(10)
CONST_HTTP_TIMEOUT_DEFAULT = const(60)
_CONST_INTERVALLE_REFRESH_FICHE = const(1 * 60 * 60)

CONST_PATH_FICHIER_DISPLAY = const('displays.json')


# Initialiser classe de buffer
BUFFER_MESSAGE = mgmessages.BufferMessage(16*1024)


def set_time():
    settime()
    print("NTP Time : ", time.gmtime())


def reboot(e=None):
    """
    Redemarre. Conserve une trace dans les fichiers exception.log et reboot.log.
    """
    print("Rebooting")
    date_line = 'Date %s (%s)' % (str(time.gmtime()), time.time())
    
    if e is not None:
        with open('exception.log', 'w') as logfile:
            logfile.write('%s\n\n---\nCaused by:\n' % date_line)
            sys.print_exception(e, logfile)
            logfile.write('\n')
    else:
        e = 'N/A'
    
    with open('reboot.log', 'a') as logfile:
        logfile.write('%s (Cause: %s)\n' % (date_line, str(e)))

    machine.reset()


async def entretien_certificat():
    try:
        return await __entretien_certificat()
    except Exception as e:
        print("Erreur entretien certificat")
        sys.print_exception(e)
    
    return False


#async def charger_timeinfo(url_relai: str):
#    print("charger_timeinfo")
#    offset = await __charger_timeinfo(url_relai)
#    print("Offset recu : %s" % offset)
#    return offset


async def verifier_renouveler_certificat(url_relai: str):
    try:
        return await __verifier_renouveler_certificat(url_relai)
    except Exception as e:
        print("Erreur verif renouveler certificat")
        sys.print_exception(e)


#async def initialiser_wifi():
#    from config import initialiser_wifi as __initialiser_wifi
#    return await __initialiser_wifi()


class Runner:
    
    def __init__(self):
        self._mode_operation = 0
        self._device_handler = DeviceHandler(self)
        self._lectures_courantes = dict()
        self._lectures_externes = dict()
        self.__url_relais = None
        self.__ui_lock = None  # Lock pour evenements UI (led, ecrans)
        
        self.__wifi_ok = False
        self.__ntp_ok = False
        self.__prochain_entretien_certificat = 0
        self.__prochain_refresh_fiche = 0
        self.__timezone_offset = None
        self.__erreurs_memory = 0  # Nombre de MemoryErrors depuis succes
        self.__erreurs_enomem = 0  # Nombre de Errno12 ENOMEM (ussl.wrap_socket) depuis succes
        self.__override_display = None
        self.__override_display_expiration = None
        self.__display_actif = False
    
    async def configurer_devices(self):
        self.__ui_lock = asyncio.Lock()
        await self._device_handler.load(self.__ui_lock)
    
    def recevoir_lectures(self, lectures):
        self._lectures_courantes = lectures

    def recevoir_lectures_externes(self, lectures):
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
        if isinstance(self.__timezone_offset, int):
            return self.__timezone_offset
        return None
    
    @property
    def ui_lock(self):
        return self.__ui_lock
    
    @property
    def wifi_ok(self):
        return self.__wifi_ok
    
    @property
    def display_actif(self):
        return self.__display_actif
    
    def reset_erreurs(self):
        self.__erreurs_memory = 0
        self.__erreurs_enomem = 0
    
    async def get_etat(self):
        try:
            senseurs = set()
            for display in self.get_configuration_display().values():
                try:
                    for ligne in display['lignes']:
                        # print("Config appareils ligne : %s" % ligne)
                        try:
                            if ligne['variable'] is not None and len(ligne['variable'].split(':')) > 1:
                                senseurs.add(ligne['variable'])
                        except KeyError:
                            pass  # Pas de variable configuree
                except KeyError:
                    pass  # Pas de lignes configurees
            senseurs = list(senseurs)
            print("Senseurs externes : %s" % senseurs)
        except (OSError, AttributeError):
            senseurs = None
        return {
            'lectures_senseurs': self._lectures_courantes,
            'displays': self._device_handler.get_output_devices(),
            'senseurs': senseurs,
        }

    async def _signature_certificat(self):
        """
        Mode d'attente de signature de certificat
        """
        certificat_recu = False
        while certificat_recu is False:
            try:
                stat(PATH_CERT)
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
                        print("OS Error " % str(ose))
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
            try:
                if self._mode_operation >= 1:
                    # Verifier etat wifi
                    self.__wifi_ok = wifi.is_wifi_ok()
                    
                    if self.__wifi_ok is False:
                        print("Restart wifi")
                        ip = await config.initialiser_wifi()
                        if ip is not None:
                            wifi_ok = True
                            print("Wifi OK : ", ip)
                        else:
                            print("Wifi echec")
                        ip = None
                
                if self.__wifi_ok is True:
                
                    if self.__ntp_ok is False:
                        set_time()
                        self.__ntp_ok = True

                    if self._mode_operation == CONST_MODE_POLLING:
                        await entretien_certificat()

            except Exception as e:
                print("Erreur entretien: %s" % e)
                sys.print_exception(e)
            finally:
                self.__ui_lock.release()
            
            if init is True:
                # Premiere run a l'initialisation
                break
            
            if self.__ntp_ok is False:
                # Tenter de charger la date
                await asyncio.sleep(15)
            else:
                await asyncio.sleep(120)

    async def charger_urls(self):
        if self.__wifi_ok is True:
            refresh = self.__prochain_refresh_fiche > 0
            # if self.__prochain_refresh_fiche < time.time():
            refresh = self.__prochain_refresh_fiche > 0

            relais = await config.charger_relais(
                self.__ui_lock, refresh=refresh, buffer=BUFFER_MESSAGE)
            self.set_relais(relais)

            if self.__prochain_refresh_fiche == 0:
                # Faire rafraichir la fiche a la prochaine boucle d'entretien
                self.__prochain_refresh_fiche = time.time()
            elif refresh is True:
                self.__prochain_refresh_fiche = _CONST_INTERVALLE_REFRESH_FICHE + time.time()

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
    
    def set_timezone_offset(self, offset):
        self.__timezone_offset = offset

    async def _polling(self):
        """
        Main thread d'execution du polling/commandes
        """
        collect()
        #if self.__prochain_refresh_fiche <= time.time():
        #    duree_thread = 60
        #else:
        #    duree_thread = CONST_DUREE_THREAD_POLLING
        duree_thread = CONST_DUREE_THREAD_POLLING
        polling_thread = PollingThread(self, BUFFER_MESSAGE, duree_thread=duree_thread)
        await polling_thread.preparer()
        await polling_thread.run()

    async def __initialisation(self):
        await config.initialisation()
        
    async def __recuperer_ca(self):
        await config.recuperer_ca(buffer=BUFFER_MESSAGE)

    async def __main(self):
        self._mode_operation = await detecter_mode_operation()
        print("Mode operation initial %d" % self._mode_operation)
        
        await led_executer_sequence(const_leds.CODE_MAIN_DEMARRAGE, executions=1, ui_lock=self.__ui_lock)
        while True:
            try:
                self._mode_operation = await detecter_mode_operation()
                print("Mode operation: %s" % self._mode_operation)

                if self._mode_operation >= CONST_MODE_CHARGER_URL_RELAIS:
                    if self.__url_relais is None or len(self.__url_relais) == 0:
                        # Recharger les relais
                        await self.charger_urls()

                # Cleanup memoire
                await asyncio.sleep_ms(1)  # Yield
                collect()
                await asyncio.sleep_ms(1)  # Yield

                if self._mode_operation == CONST_MODE_INIT:
                    await self.__initialisation()
                elif self.__wifi_ok is False:
                    await led_executer_sequence(const_leds.CODE_WIFI_NON_CONNECTE, 1, self.__ui_lock)
                    await asyncio.sleep(30)
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
                    print("Mode operation non supporte : %d" % self._mode_operation)
                    await led_executer_sequence(const_leds.CODE_MAIN_OPERATION_INCONNUE, executions=None)

            except OSError as e:
                if e.errno == 12:
                    self.__erreurs_enomem += 1
                    if self.__erreurs_enomem >= CONST_NB_ERREURS_RESET:
                        print("ENOMEM count:%d, reset" % self.__erreurs_enomem)
                        await led_executer_sequence(
                            const_leds.CODE_ERREUR_MEMOIRE, executions=1, ui_lock=self.__ui_lock)
                        reboot(e)
                    
                    print("Erreur memoire no %d" % self.__erreurs_enomem)
                    sys.print_exception(e)
                    collect()
                    self.afficher_info()
                    await asyncio.sleep_ms(500)
                    continue

                else:
                    print("OSError main")
                    sys.print_exception(e)
                    collect()
                    self.afficher_info()                    
                    await asyncio.sleep(60)

            except MemoryError as e:
                self.__erreurs_memory += 1
                if self.__erreurs_memory >= CONST_NB_ERREURS_RESET:
                    print("MemoryError count:%d, reset" % self.__erreurs_memory)
                    reboot(e)
                
                print("MemoryError %s" % e)
                sys.print_exception(e)
                print("Erreur memoire no %d\n%s" % (self.__erreurs_memory, mem_info()))
                collect()
                self.afficher_info()
                await asyncio.sleep_ms(50)
            except Exception as e:
                print("Erreur main")
                collect()
                sys.print_exception(e)
                self.afficher_info()                

            # Erreur execution ou changement runlevel
            await led_executer_sequence(const_leds.CODE_MAIN_ERREUR_GENERALE, 4, self.__ui_lock)
    
    async def run(self):
        self.afficher_info()
        
        # Charger configuration
        await self.configurer_devices()

        # Demarrer thread entretien (wifi, date, configuration)
        await self.entretien(init=True)
        asyncio.create_task(self.entretien())

        # Task devices
        asyncio.create_task(self._device_handler.run(
            self.__ui_lock, self.recevoir_lectures, self.get_feeds, 2000))

        # Executer main loop
        await self.__main()

    def afficher_info(self):
        print(CONST_INFO_SEP)
        print("Heure %s" % str(time.gmtime()))
        print("Memoire")
        mem_info()
        print(CONST_INFO_SEP + '\n')


async def main():
    runner = Runner()
    await runner.run()


if __name__ == '__main__':
    asyncio.run(main())
