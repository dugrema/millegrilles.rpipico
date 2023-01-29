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
    
    async def ajouter_programme(self, programme):
        self._programmes[programme.programme_id] = programme
        asyncio.create_task(programme.run())
        print("Programme %s demarre" % programme.programme_id)

    async def arreter_programme(programme_id):
        programme = self._programmes[programme_id]
        await programme.stop()
        del self._programmes[programme_id]
        print("Programme %s arrete" % programme_id)

    async def initialiser(self):
        try:
            with open('programmes.json') as fichier:
                config_programmes = load(fichier)
        except OSError:
            return  # Le fichier n'existe pas, rien a faire

        for programme in config_programmes['programmes']:
            programme_id = programme['programme_id']
            print("Charger programme %s" % programme_id)
            programme_class = import_driver(programme['class'])
            args = programme.get('args') or dict()
            programme_instance = programme_class(self._appareil, programme_id, args)
            await self.ajouter_programme(programme_instance)
            

""" Classe abstraite pour un programme """
class ProgrammeActif:

    def __init__(self, appareil, programme_id, args=None):
        self._appareil = appareil
        self._programme_id = programme_id
        self._args = args
        self._actif = True

    @property
    def programme_id(self):
        return self._programme_id
    
    def get_senseurs(self):
        """ Retourne la liste des senseurs requis """
        return None

    async def run(self):
        raise('Not Implemented')

    async def stop(self):
        self._actif = False

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
