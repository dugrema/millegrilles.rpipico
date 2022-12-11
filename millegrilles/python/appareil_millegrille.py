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

import const_leds
import config
import feed_display
import mgmessages
import wifi

from polling_messages import polling_thread
from ledblink import led_executer_sequence
from handler_devices import DeviceHandler
from certificat import entretien_certificat as __entretien_certificat                       
from message_inscription import run_inscription, \
     verifier_renouveler_certificat as __verifier_renouveler_certificat


from config import \
     CONST_MODE_INIT, \
     CONST_MODE_RECUPERER_CA, \
     CONST_MODE_CHARGER_URL_RELAIS, \
     CONST_MODE_SIGNER_CERTIFICAT, \
     CONST_MODE_POLLING, \
     detecter_mode_operation

CONST_INFO_SEP = const(' ---- INFO ----')
CONST_NB_ERREURS_RESET = const(10)
CONST_HTTP_TIMEOUT_DEFAULT = const(60)

CONST_PATH_FICHIER_DISPLAY = const('displays.json')


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
        self._device_handler = DeviceHandler()
        self._lectures_courantes = dict()
        self._lectures_externes = dict()
        self.__url_relais = None
        self.__url_relai_courant = None
        self.__ui_lock = None  # Lock pour evenements UI (led, ecrans)
        self.__erreurs_memoire = 0
        
        self.__wifi_ok = False
        self.__ntp_ok = False
        self.__prochain_entretien_certificat = 0

    
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
        # await config.init_cle_privee()
        
        try:
            url_relai = self.__url_relais.pop()
            await run_inscription(url_relai, self.__ui_lock)
        except (AttributeError, IndexError):
            print("Aucun url relais")
            self.__url_relais = None  # Garanti un chargement via entretien

    def feed_default(self):
        return feed_display.FeedDisplayDefault(self)

    def feed_custom(self, name, config):
        return feed_display.FeedDisplayCustom(self, name, config)

    def get_feeds(self, name=None):
        if name is None:
            return self.feed_default()
        try:
            config_feed = self.get_configuration_display()[name]
            return self.feed_custom(name, config_feed)
        except (AttributeError, OSError, KeyError, TypeError):
            print("Feed %s inconnu, defaulting" % name)
            return self.feed_default()
    
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
                        if self.__prochain_entretien_certificat < time.time():
                            if await entretien_certificat() is True:
                                self.__prochain_entretien_certificat = time.time() + 7200
                            
                        # Faire entretien
                        pass

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
        fiche = await config.charger_fiche()
        info_cert = await mgmessages.verifier_message(fiche)
        if 'core' in info_cert['roles']:
            url_relais = [app['url'] for app in fiche['applications']['senseurspassifs_relai'] if app['nature'] == 'dns']
            self.__url_relais = url_relais
            print("URL relais : %s" % self.__url_relais)

    def get_configuration_display(self):
        try:
            with open(CONST_PATH_FICHIER_DISPLAY, 'rb') as fichier:
                return json.load(fichier)
        except OSError:
            pass  # Fichier absent
        
    def set_configuration_display(self, configuration: dict):
        # print('Maj configuration display')
        with open(CONST_PATH_FICHIER_DISPLAY, 'wb') as fichier:
            json.dump(configuration, fichier)

    async def _polling(self):
        """
        Main thread d'execution du polling/commandes
        """
        while self._mode_operation == CONST_MODE_POLLING:
            # Rotation relais pour en trouver un qui fonctionne
            # Entretien va rafraichir la liste via la fiche
            try:
                if self.__url_relai_courant is None:
                    self.__url_relai_courant = self.__url_relais.pop(0)
                
                http_timeout = config.get_http_timeout()
                # print("http timeout : %d" % http_timeout)
                
                # Verifier si on peut renouveler le certificat
                await verifier_renouveler_certificat(self.__url_relai_courant)
                # Reset erreurs memoire, requete SSL executee avec succes
                self.__erreurs_memoire = 0
                
                # Polling
                await polling_thread(self, self.__url_relai_courant, http_timeout, self.get_etat)
                
            except OSError as ose:
                # Erreur OS (e.g. 12:memoire ou 6:WIFI), sortir de polling
                raise ose
            except (AttributeError, IndexError) as e:
                print("Aucun url relais")
                self.__url_relais = None  # Garanti un chargement via entretien
                raise e  # Sortir de la boucle pour recharger un relai
            except Exception as e:
                print("Erreur polling")
                sys.print_exception(e)
                # await ledblink.led_executer_sequence(CODE_POLLING_ERREUR_GENERALE, executions=2, ui_lock=self.__ui_lock)
                    
            await asyncio.sleep_ms(100)

    async def __initialisation(self):
        await config.initialisation()
        
    async def __recuperer_ca(self):
        await config.recuperer_ca()

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
                await asyncio.sleep(5)
                collect()
                await asyncio.sleep(1)

                if self._mode_operation == CONST_MODE_INIT:
                    await self.__initialisation()
                elif self._mode_operation == CONST_MODE_RECUPERER_CA:
                    await self.__recuperer_ca()
                elif self._mode_operation == CONST_MODE_SIGNER_CERTIFICAT:
                    await self._signature_certificat()
                elif self._mode_operation == CONST_MODE_POLLING:
                    await self._polling()
                else:
                    print("Mode operation non supporte : %d" % self._mode_operation)
                    await led_executer_sequence(const_leds.CODE_MAIN_OPERATION_INCONNUE, executions=None)

            except OSError as e:
                if e.errno == 12:
                    self.__erreurs_memoire = self.__erreurs_memoire + 1
                    if self.__erreurs_memoire >= CONST_NB_ERREURS_RESET:
                        print("Trop d'erreur memoire, reset")
                        reboot(e)
                    
                    print("Erreur memoire no %d\n%s" % (self.__erreurs_memoire, mem_info()))
                    sys.print_exception(e)
                    collect()
                    await led_executer_sequence(const_leds.CODE_ERREUR_MEMOIRE, executions=1, ui_lock=self.__ui_lock)
                    await asyncio.sleep(10)
                else:
                    print("OSError main")
                    sys.print_exception(e)
                    await asyncio.sleep(60)
            except MemoryError as e:
                self.__erreurs_memoire = self.__erreurs_memoire + 1
                if self.__erreurs_memoire >= CONST_NB_ERREURS_RESET:
                    print("Trop d'erreur memoire, reset")
                    reboot(e)
                
                print("MemoryError %s" % e)
                sys.print_exception(e)
                print("Erreur memoire no %d\n%s" % (self.__erreurs_memoire, mem_info()))
                collect()
                print("Memoire post collect\n%s" % mem_info())
                await asyncio.sleep(10)
            except Exception as e:
                print("Erreur main")
                sys.print_exception(e)

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
            self.__ui_lock, self.recevoir_lectures, self.get_feeds))

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
