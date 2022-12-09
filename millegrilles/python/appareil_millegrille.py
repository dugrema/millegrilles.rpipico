# Programme appareil millegrille
import uasyncio as asyncio
import urequests2 as requests

# Methodes de gestion de memoire (preload)
from gc import collect
from micropython import mem_info
from machine import reset as machine_reset
from sys import print_exception

from ledblink import led_executer_sequence

from handler_devices import DeviceHandler
from wifi import is_wifi_ok
from mgmessages import verifier_message

CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_CHARGER_URL_RELAIS = const(3)
CONST_MODE_SIGNER_CERTIFICAT = const(4)
CONST_MODE_POLLING = const(99)

CONST_HTTP_TIMEOUT_DEFAULT = const(60)

CONST_PATH_FICHIER_CONN = const('conn.json')
CONST_PATH_FICHIER_DISPLAY = const('displays.json')
CONST_CHAMP_HTTP_INSTANCE = const('http_instance')

# Erreurs
CODE_MAIN_DEMARRAGE = const((4,1))
CODE_MAIN_OPERATION_INCONNUE = const((1,1))
CODE_CONFIG_INITIALISATION = const((1,2))
CODE_MAIN_ERREUR_GENERALE = const((1,3))
CODE_POLLING_ERREUR_GENERALE = const((2,1))
CODE_ERREUR_MEMOIRE = const((4,2))

mode_operation = 0


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


async def recuperer_ca():
    from mgmessages import sauvegarder_ca
    
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
    from mgmessages import PATH_CLE_PRIVEE, generer_cle_secrete
    try:
        stat(PATH_CLE_PRIVEE)
    except OSError:
        generer_cle_secrete()
        print("Cle privee initialisee")


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


def set_time():
    import time
    from ntptime import settime
    
    settime()
    print("NTP Time : ", time.gmtime())


class Runner:
    
    def __init__(self):
        self._mode_operation = 0
        self._device_handler = DeviceHandler()
        self._lectures_courantes = dict()
        self._lectures_externes = dict()
        self.__url_relais = None
        self.__ui_lock = None  # Lock pour evenements UI (led, ecrans)
        self.__erreurs_memoire = 0
    
    async def configurer_devices(self):
        from json import load
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
        from message_inscription import run_inscription
        await init_cle_privee()
        
        try:
            url_relai = self.__url_relais.pop()
            await run_inscription(url_relai, get_user_id(), self.__ui_lock)
        except (AttributeError, IndexError):
            print("Aucun url relais")
            self.__url_relais = None  # Garanti un chargement via entretien

    def feed_default(self):
        from feed_display import FeedDisplayDefault
        return FeedDisplayDefault(self)

    def feed_custom(self, name, config):
        from feed_display import FeedDisplayCustom
        return FeedDisplayCustom(self, name, config)

    def get_feeds(self, name=None):
        if name is None:
            return self.feed_default()
        try:
            config_feed = self.get_configuration_display()[name]
            return self.feed_custom(name, config_feed)
        except (AttributeError, OSError, KeyError, TypeError):
            print("Feed %s inconnu, defaulting" % name)
            return self.feed_default()
    
    async def entretien(self):
        """
        Thread d'entretien
        """
        wifi_ok = False
        ntp_ok = False
        
        while True:
            print("Entretien mode %d" % self._mode_operation)
            await self.__ui_lock.acquire()
            try:
                if self._mode_operation >= 1:
                    # Verifier etat wifi
                    wifi_ok = is_wifi_ok()
                    
                    if wifi_ok is False:
                        print("Restart wifi")
                        ip = await initialiser_wifi()
                        if ip is not None:
                            wifi_ok = True
                            print("Wifi OK : ", ip)
                        else:
                            print("Wifi echec")
                
                if wifi_ok is True:
                
                    if ntp_ok is False:
                        set_time()
                        ntp_ok = True

                    if self._mode_operation == CONST_MODE_POLLING:
                        # Faire entretien
                        pass

            except Exception as e:
                print("Erreur entretien: %s" % e)
            finally:
                self.__ui_lock.release()
            
            await asyncio.sleep(120)

    async def charger_urls(self):
        fiche = await charger_fiche()
        info_cert = await verifier_message(fiche)
        if 'core' in info_cert['roles']:
            url_relais = [app['url'] for app in fiche['applications']['senseurspassifs_relai'] if app['nature'] == 'dns']
            self.__url_relais = url_relais
            print("URL relais : %s" % self.__url_relais)

    def get_configuration_display(self):
        from json import load
        try:
            with open(CONST_PATH_FICHIER_DISPLAY, 'rb') as fichier:
                return load(fichier)
        except OSError:
            pass  # Fichier absent
        
    def set_configuration_display(self, configuration: dict):
        from json import dump
        # print('Maj configuration display')
        with open(CONST_PATH_FICHIER_DISPLAY, 'wb') as fichier:
            dump(configuration, fichier)

    async def _polling(self):
        """
        Main thread d'execution du polling/commandes
        """
        from polling_messages import polling_thread

        while self._mode_operation == CONST_MODE_POLLING:
            # Rotation relais pour en trouver un qui fonctionne
            # Entretien va rafraichir la liste via la fiche
            try:
                url_relai = self.__url_relais.pop(0)
                http_timeout = get_http_timeout()
                # print("http timeout : %d" % http_timeout)
                
                await polling_thread(self, url_relai, http_timeout, self.get_etat)
                
                # Reset erreurs memoire, cycle execute avec succes
                self.__erreurs_memoire = 0
            except OSError as ose:
                # Erreur OS (e.g. 12:memoire ou 6:WIFI), sortir de polling
                raise ose
            except (AttributeError, IndexError) as e:
                print("Aucun url relais")
                self.__url_relais = None  # Garanti un chargement via entretien
                raise e  # Sortir de la boucle pour recharger un relai
            except Exception as e:
                print("Erreur polling")
                print_exception(e)
                # await ledblink.led_executer_sequence(CODE_POLLING_ERREUR_GENERALE, executions=2, ui_lock=self.__ui_lock)
                    
            await asyncio.sleep_ms(100)

    async def __main(self):
        self._mode_operation = await detecter_mode_operation()
        print("Mode operation initial %d" % mode_operation)
        
        await led_executer_sequence(CODE_MAIN_DEMARRAGE, executions=1, ui_lock=self.__ui_lock)
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
                    await initialisation()
                elif self._mode_operation == CONST_MODE_RECUPERER_CA:
                    await recuperer_ca()
                elif self._mode_operation == CONST_MODE_SIGNER_CERTIFICAT:
                    await self._signature_certificat()
                elif self._mode_operation == CONST_MODE_POLLING:
                    await self._polling()
                else:
                    print("Mode operation non supporte : %d" % self._mode_operation)
                    await led_executer_sequence(CODE_MAIN_OPERATION_INCONNUE, executions=None)

            except OSError as ose:
                if ose.errno == 12:
                    self.__erreurs_memoire = self.__erreurs_memoire + 1
                    print("Erreur memoire no %d\n%s" % (self.__erreurs_memoire, mem_info()))
                    print_exception(ose)
                    collect()
                    await led_executer_sequence(CODE_ERREUR_MEMOIRE, executions=1, ui_lock=self.__ui_lock)
                    await asyncio.sleep(10)
                    if self.__erreurs_memoire >= 10:
                        print("Trop d'erreur, reset")
                        machine_reset()
                else:
                    print("OSError main")
                    print_exception(ose)
                    await asyncio.sleep(60)

            except Exception as e:
                print("Erreur main")
                print_exception(e)
            
            await led_executer_sequence(CODE_MAIN_ERREUR_GENERALE, 4, self.__ui_lock)
    
    async def run(self):
        # Charger configuration
        await self.configurer_devices()

        # Demarrer thread entretien (wifi, date, configuration)
        asyncio.create_task(self.entretien())

        # Task devices
        asyncio.create_task(self._device_handler.run(
            self.__ui_lock, self.recevoir_lectures, self.get_feeds))

        # Executer main loop
        await self.__main()


async def main():
    runner = Runner()
    await runner.run()


if __name__ == '__main__':
    asyncio.run(main())
