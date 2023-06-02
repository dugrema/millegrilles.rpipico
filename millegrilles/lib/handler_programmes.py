import time
import uasyncio as asyncio
from ujson import load
from handler_devices import import_driver


class ProgrammesHandler:
    """ Handler de programmes. Conserve liste. """
    
    def __init__(self, appareil):
        self._appareil = appareil
        self._programmes = dict()
    
    @property
    def programmes(self):
        return self._programmes
    
    def get_senseurs(self):
        """ @return: Liste senseurs externes requis """
        senseurs = set()

        for programme in self._programmes.values():
            try:
                senseurs.extend(programme.get_senseurs())
            except AttributeError:
                pass

        return list(senseurs)
    
    async def ajouter_programme(self, configuration: dict):
        actif = configuration.get('actif') or False

        if actif is False:
            # On ne configure / charge pas un programme inactif
            return None

        try:
            existant = self._programmes[configuration['programme_id']]
            # Le programme existe, on le met a jour
            await existant.maj(configuration)
            print("Programme %s maj" % existant.programme_id)
        except KeyError:
            # Programme n'existe pas
            programme_id = configuration['programme_id']
            print("Charger programme %s" % programme_id)
            programme_class = import_driver(configuration['class'])
            args = configuration.get('args') or dict()
            programme_instance = programme_class(self._appareil, programme_id, args)

            # Ajouter programme et demarrer thread
            self._programmes[programme_instance.programme_id] = programme_instance

            # Demarrer l'execution du programme
            asyncio.create_task(programme_instance.run_task())
            print("Programme %s demarre" % programme_id)

    async def arreter_programme(self, programme_id):
        try:
            programme = self._programmes[programme_id]
            await programme.stop()
        except (KeyError, TypeError):
            pass  # Programme deja arrete
        finally:
            try:
                del self._programmes[programme_id]
            except KeyError:
                pass  # Ok

        print("Programme %s arrete" % programme_id)

    async def initialiser(self):
        try:
            with open('programmes.json') as fichier:
                config_programmes = load(fichier)
        except OSError:
            return  # Le fichier n'existe pas, rien a faire

        for programme in config_programmes.values():  # config_programmes['programmes']:
            # programme_id = programme['programme_id']
            # print("Charger programme %s" % programme_id)
            # programme_class = import_driver(programme['class'])
            # args = programme.get('args') or dict()
            # programme_instance = programme_class(self._appareil, programme_id, args)
            await self.ajouter_programme(programme)

    async def get_notifications(self):
        notifications = list()
        for programme_id, programme in self._programmes.items():
            try:
                notification = await programme.generer_message()
                if notification is not None:
                    print("!handler_programmes! notification %s" % notification)
                    notifications.append(notification)
            except Exception as e:
                print("get_notifications Error %s" % e)
                pass  # Programme sans support de notification
        if len(notifications) == 0:
            return None
        print("!handler_programmes! %d notifications" % len(notifications))
        return notifications


class ProgrammeActif:
    """ Classe abstraite pour un programme """

    def __init__(self, appareil, programme_id, args=None, intervalle=5000):
        self._appareil = appareil
        self._programme_id = programme_id
        self.__intervalle = intervalle
        self._arreter = asyncio.Event()
        self.__reloading = False
        self.__intervalle_onetime = None  # Permet de faire un override de l'intervalle

        if args is not None:
            self.charger_args(args)

    def charger_args(self, args):
        pass

    @property
    def actif(self):
        return not self._arreter.is_set()

    @property
    def programme_id(self):
        return self._programme_id
    
    def get_senseurs(self):
        """ Retourne la liste des senseurs requis """
        return None

    @property
    def intervalle(self):
        return self.__intervalle

    def set_intervalle_onetime(self, intervalle_ms):
        """ Set override de sleep pour le prochain cycle """
        if intervalle_ms < 0:
            intervalle_ms = 1000  # Minimum 1 seconde
        self.__intervalle_onetime = intervalle_ms

    async def run_task(self):
        print("Programme %s demarre" % self._programme_id)
        while not self._arreter.is_set():
            await self.loop()
            try:
                await self.wait()
            except ProgrammeInterrompu as e:
                if self._arreter.is_set() is False:
                    # Situation anormale
                    raise e

            if self.__reloading is True:
                # Toggle reloading flag, clear _arreter pour loop
                print("Programme %s redemarre" % self._programme_id)
                self.__reloading = False
                self._arreter.clear()

        print("Programme %s arrete" % self._programme_id)

    async def loop(self):
        raise Exception('loop() Not Implemented')

    async def maj(self, configuration: dict):
        self.charger_args(configuration['args'])

        actif = configuration.get('actif') or False
        if actif is True and self._arreter.is_set():
            print("Redemarrer programme %s" % self._programme_id)
            self._arreter.clear()
            asyncio.create_task(self.run_task())
        elif actif is False and self._arreter.is_set() is False:
            print("Arreter programme %s" % self._programme_id)
            self.stop()
        else:
            # Trigger un reload immediat de la thread
            print("Reload programme %s" % self._programme_id)
            self.__reloading = True
            self._arreter.set()

    def stop(self):
        print("Arreter programme %s" % self._programme_id)
        self._arreter.set()

    async def wait(self):
        try:
            attente = self.__intervalle

            if self.__intervalle_onetime is not None:
                if self.__intervalle_onetime < self.__intervalle:
                    attente = self.__intervalle_onetime
                self.__intervalle_onetime = None  # Reset

            await asyncio.wait_for_ms(self._arreter.wait(), attente)
            raise ProgrammeInterrompu()
        except asyncio.TimeoutError:
            pass  # OK

    def time_localtime(self, ts=None):
        if ts is None:
            ts = time.time()

        tz = self._appareil.timezone
        if tz is not None:
            ts = ts + tz

        return time.gmtime(ts)

    def time_localmktime(self, annee, mois, jour, heure, minute, seconde):
        """ Change le timestamp UTC avec timezone configuree. """
        ts = time.mktime((annee, mois, jour, heure, minute, seconde, None, None))

        tz = self._appareil.timezone
        if tz is not None:
            # Soustraire TZ pour ajuster a temps GMT
            ts = ts - tz

        return ts


class ProgrammeInterrompu(Exception):
    pass
