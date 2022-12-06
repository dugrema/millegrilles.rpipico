# Programme appareil millegrille
import json
import ledblink
import sys
import time
import uasyncio as asyncio

from gc import collect
from machine import reset as machine_reset

from handler_devices import DeviceHandler
from wifi import is_wifi_ok

CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_CHARGER_URL_RELAIS = const(3)
CONST_MODE_SIGNER_CERTIFICAT = const(4)
CONST_MODE_POLLING = const(99)

CONST_HTTP_TIMEOUT_DEFAULT = const(60)

CONST_PATH_FICHIER_CONN = const('conn.json')
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
    await ledblink.led_executer_sequence(CODE_CONFIG_INITIALISATION, executions=None)


async def initialiser_wifi():
    import wifi
    wifi_ok = False
    for _ in range(0, 5):
        try:
            status = await wifi.connect_wifi()
            return status
        except (RuntimeError, OSError) as e:
            print("Wifi error %s" % e)
            await asyncio.sleep(3)
    if wifi_ok is False:
        raise RuntimeError('wifi')
            

def get_idmg():
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return json.load(fichier)['idmg']


def get_user_id():
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return json.load(fichier)['user_id']


# Recuperer la fiche (CA, chiffrage, etc)
async def charger_fiche():
    import urequests2 as requests
    
    try:
        fiche_url = get_url_instance() + '/fiche.json'
    except OSError:
        print("Fichier connexion absent")
        return

    # Downloader la fiche
    print("Recuperer fiche a %s" % fiche_url)
    reponse = await requests.get(fiche_url)
    try:
        await asyncio.sleep(0)  # Yield
        if reponse.status_code != 200:
            raise Exception("http %d" % reponse.status_code)
        fiche_json = await reponse.json()
        print("Fiche recue")
    finally:
        reponse.close()
        
    return fiche_json


def get_url_instance():
    with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
        return json.load(fichier)[CONST_CHAMP_HTTP_INSTANCE]


def get_http_timeout():
    try:
        with open(CONST_PATH_FICHIER_CONN, 'rb') as fichier:
            return json.load(fichier)['http_timeout']
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
    import os
    from mgmessages import PATH_CLE_PRIVEE, generer_cle_secrete
    
    try:
        os.stat(PATH_CLE_PRIVEE)
    except OSError:
        generer_cle_secrete()
        print("Cle privee initialisee")


async def detecter_mode_operation():
    # Si wifi.txt/idmg.txt manquants, on est en mode initial.
    import os
    try:
        os.stat(CONST_PATH_FICHIER_CONN)
    except:
        print("Mode initialisation")
        return CONST_MODE_INIT
    
    try:
        os.stat('certs/ca.der')
    except:
        print("Mode recuperer ca.der")
        return CONST_MODE_RECUPERER_CA
    
    try:
        os.stat("certs/cert.pem")
    except:
        print("Mode signer certificat")
        return CONST_MODE_SIGNER_CERTIFICAT

    return CONST_MODE_POLLING  # Mode polling


def set_time():
    from ntptime import settime
    print("NTP")
    settime()
    print("Time : ", time.gmtime())
    print("Time epoch %s" % time.time())


class Runner:
    
    def __init__(self):
        self._mode_operation = 0
        self._device_handler = DeviceHandler()
        self._lectures_courantes = dict()
        self.__url_relais = None
        self.__ui_lock = None  # Lock pour evenements UI (led, ecrans)
        self.__erreurs_memoire = 0
    
    async def configurer_devices(self):
        self.__ui_lock = asyncio.Lock()
        await self._device_handler.load(self.__ui_lock)
    
    def recevoir_lectures(self, lectures):
        # print("recevoir_lectures: %s" % lectures)
        self._lectures_courantes = lectures
    
    async def get_etat(self):
        return {
            'lectures_senseurs': self._lectures_courantes,
            'displays': self._device_handler.get_output_devices(),
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
        try:
            wifi_ip = self._lectures_courantes['rp2pico/wifi']['valeur_str']
        except KeyError:
            print("No wifi lectures")
            #from wifi import get_etat_wifi
            #wifi_ip = get_etat_wifi()['ip']
            wifi_ip = 'N/A'
        data_lignes = ['WIFI IP', wifi_ip]
        while len(data_lignes) > 0:
            yield data_lignes.pop(0)
        # return []
        #return None

    def get_feeds(self, name=None):
        return self.feed_default
    
    async def entretien(self):
        """
        Thread d'entretien
        """
        wifi_ok = False
        ntp_ok = False
        
        while True:
            print("Entretien mode %d, date %s" % (self._mode_operation, time.time()))
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
            
            await asyncio.sleep(20)

    async def charger_urls(self):
        from mgmessages import verifier_message
        fiche = await charger_fiche()
        info_cert = await verifier_message(fiche)
        print("Info cert fiche : %s" % info_cert)
        if 'core' in info_cert['roles']:
            url_relais = [app['url'] for app in fiche['applications']['senseurspassifs_relai'] if app['nature'] == 'dns']
            self.__url_relais = url_relais
            print("URL relais : %s" % self.__url_relais)

    async def _polling(self):
        """
        Main thread d'execution du polling/commandes
        """
        import polling_messages
        
        while self._mode_operation == CONST_MODE_POLLING:
            # Rotation relais pour en trouver un qui fonctionne
            # Entretien va rafraichir la liste via la fiche
            try:
                url_relai = self.__url_relais.pop(0)
                http_timeout = get_http_timeout()
                print("http timeout : %d" % http_timeout)
                
                await polling_messages.polling_thread(url_relai, http_timeout, self.get_etat)
                
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
                sys.print_exception(e)
                await ledblink.led_executer_sequence(CODE_POLLING_ERREUR_GENERALE, executions=2, ui_lock=self.__ui_lock)
                    
            await asyncio.sleep_ms(100)

    async def __main(self):
        self._mode_operation = await detecter_mode_operation()
        print("Mode operation initial %d" % mode_operation)
        
        await ledblink.led_executer_sequence(CODE_MAIN_DEMARRAGE, executions=1, ui_lock=self.__ui_lock)
        while True:
            try:
                self._mode_operation = await detecter_mode_operation()
                print("Mode operation: %s" % self._mode_operation)

                if self._mode_operation >= CONST_MODE_CHARGER_URL_RELAIS:
                    if self.__url_relais is None or len(self.__url_relais) == 0:
                        # Recharger les relais
                        await self.charger_urls()

                # Cleanup memoire
                await asyncio.sleep(0.5)
                collect()
                await asyncio.sleep(2)

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
                    await ledblink.led_executer_sequence(CODE_MAIN_OPERATION_INCONNUE, executions=None)

            except OSError as ose:
                if ose.errno == 12:
                    self.__erreurs_memoire = self.__erreurs_memoire + 1
                    print("Erreur memoire no %d" % self.__erreurs_memoire)
                    collect()
                    await ledblink.led_executer_sequence(CODE_ERREUR_MEMOIRE, executions=1, ui_lock=self.__ui_lock)
                    await asyncio.sleep(10)
                    if self.__erreurs_memoire >= 10:
                        print("Trop d'erreur, reset")
                        machine_reset()
                else:
                    print("OSError main")
                    sys.print_exception(e)

            except Exception as e:
                print("Erreur main")
                sys.print_exception(e)
            
            await ledblink.led_executer_sequence(CODE_MAIN_ERREUR_GENERALE, 4, self.__ui_lock)
    
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
