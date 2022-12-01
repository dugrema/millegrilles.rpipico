# Programme appareil millegrille
import uasyncio as asyncio
import ledblink
import ntptime
import sys
import time

from handler_devices import DeviceHandler
from wifi import is_wifi_ok

import mgmessages

CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_SIGNER_CERTIFICAT = const(3)
CONST_MODE_POLLING = const(99)

CONST_HTTP_TIMEOUT_DEFAULT = const(60)

PATH_FICHIER_CONN = const('conn.json')
PATH_FICHIER_IDMG = const('idmg.txt')
PATH_FICHIER_WIFI = const('wifi.txt')

mode_operation = 0


async def initialisation():
    """
    Mode initial si aucun parametres charges
    """
    await ledblink.led_executer_sequence([1,2], executions=None)


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
            

async def get_idmg():
    with open(PATH_FICHIER_IDMG, 'r') as fichier:
        idmg = fichier.read()
    asyncio.sleep(0)  # Yield
    idmg = idmg.strip()
    return idmg


# Recuperer la fiche (CA, chiffrage, etc)
async def charger_fiche():
    import json
    import urequests

    await initialiser_wifi()

    try:
        fiche_url = get_url_relai() + '/fiche.json'
    except OSError:
        print("Fichier connexion absent")
        return

    # Downloader la fiche
    print("Recuperer fiche a %s" % fiche_url)
    reponse = urequests.get(fiche_url)
    await asyncio.sleep(0)  # Yield
    if reponse.status_code != 200:
        raise Exception("http %d" % reponse.status_code)
    fiche_json = reponse.json()
    print("Fiche recue")
    
    return fiche_json


def get_url_relai():
    import json
    with open(PATH_FICHIER_CONN, 'rb') as fichier:
        url_relai = json.load(fichier)['relai']
    return url_relai


def get_http_timeout():
    import json
    try:
        with open(PATH_FICHIER_CONN, 'rb') as fichier:
            return json.load(fichier)['polling_timeout']
    except Exception:
        pass
    
    return CONST_HTTP_TIMEOUT_DEFAULT


async def recuperer_ca():
    print("Init millegrille")
    idmg, fiche = await asyncio.gather(
        get_idmg(),
        charger_fiche(),
    )
    del fiche['_millegrille']
    
    if fiche['idmg'] != idmg:
        raise Exception('IDMG mismatch')
    
    print("IDMG OK : %s" % idmg)
    
    # Sauvegarder le certificat CA
    mgmessages.sauvegarder_ca(fiche['ca'], idmg)


async def init_cle_privee(force=False):
    import os
    try:
        os.stat(mgmessages.PATH_CLE_PRIVEE)
    except OSError:
        mgmessages.generer_cle_secrete()
        print("Cle privee initialisee")


async def signature_certificat():
    """
    Mode d'attente de signature de certificat
    """
    import message_inscription
    await initialiser_wifi()
    await init_cle_privee()
    
    await message_inscription.run_inscription(get_url_relai())


async def detecter_mode_operation():
    # Si wifi.txt/idmg.txt manquants, on est en mode initial.
    import os
    try:
        os.stat(PATH_FICHIER_WIFI)
        os.stat(PATH_FICHIER_IDMG)
        os.stat(PATH_FICHIER_CONN)
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


class Runner:
    
    def __init__(self):
        self._mode_operation = 0
        self._device_handler = DeviceHandler()
        self._lectures_courantes = dict()
    
    async def configurer_devices(self):
        await self._device_handler.load()
    
    def recevoir_lectures(self, lectures):
        # print("recevoir_lectures: %s" % lectures)
        self._lectures_courantes = lectures
    
    async def get_etat(self):
        return {'lectures_senseurs': self._lectures_courantes}
    
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
            print("Entretien mode %d" % self._mode_operation)
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
                    
                    if wifi_ok is True and ntp_ok is False:
                        print("NTP")
                        ntptime.settime()
                        ntp_ok = True
                        print("Time : ", time.gmtime())
                        print("Time epoch %s" % time.time())
                
                if self._mode_operation == CONST_MODE_POLLING:
                    # Faire entretien
                    pass
            except Exception as e:
                print("Erreur entretien: %s" % e)
            
            await asyncio.sleep(20)

    async def _polling(self):
        """
        Main thread d'execution du polling/commandes
        """
        import polling_messages
        while self._mode_operation == CONST_MODE_POLLING:
            try:
                http_timeout = get_http_timeout()
                print("http timeout : %d" % http_timeout)
                await polling_messages.polling_thread(http_timeout, self.get_etat)
            except Exception as e:
                print("Erreur polling")
                sys.print_exception(e)
                await ledblink.led_executer_sequence([2, 1], 2)
            await asyncio.sleep(2)

    async def __main(self):
        self._mode_operation = await detecter_mode_operation()
        print("Mode operation initial %d" % mode_operation)
        
        await ledblink.led_executer_sequence([4], executions=1)
        while True:
            try:
                self._mode_operation = await detecter_mode_operation()
                print("Mode operation: %s" % self._mode_operation)

                if self._mode_operation == CONST_MODE_INIT:
                    await initialisation()
                elif self._mode_operation == CONST_MODE_RECUPERER_CA:
                    await recuperer_ca()
                elif self._mode_operation == CONST_MODE_SIGNER_CERTIFICAT:
                    await signature_certificat()
                elif self._mode_operation == CONST_MODE_POLLING:
                    await self._polling()
                else:
                    print("Mode operation non supporte : %d" % self._mode_operation)
                    await ledblink.led_executer_sequence([1,1], executions=None)
            except Exception as e:
                print("Erreur main")
                sys.print_exception(e)
            
            await ledblink.led_executer_sequence([1, 3], 4)
    
    async def run(self):
        # Demarrer thread entretien (wifi, date, configuration)
        asyncio.create_task(self.entretien())
        
        # Charger configuration
        await self.configurer_devices()
        asyncio.create_task(self._device_handler.run(self.recevoir_lectures, self.get_feeds))

        # Executer main loop
        await self.__main()


async def main():
    runner = Runner()
    await runner.run()


if __name__ == '__main__':
    asyncio.run(main())
