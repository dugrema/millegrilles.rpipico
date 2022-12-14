import uasyncio as asyncio
from sys import print_exception

from handler_devices import Driver


class OutputLignes(Driver):
    
    def __init__(self, appareil, params, busses, ui_lock: asyncio.Event, nb_chars=16, nb_lignes=2, duree_afficher_datetime=10):
        super().__init__(appareil, params, busses, ui_lock)
        self._instance = None
        self.__busses = busses
        self._nb_lignes = nb_lignes
        self._nb_chars = nb_chars
        self.__duree_afficher_datetime = duree_afficher_datetime

    async def load(self):
        self._instance = self._get_instance()
        
    def _get_instance(self):
        raise Exception('Not implemented')

    async def preparer_ligne(self, data, flag=None):
        raise Exception('Not implemented')

    async def show(self, attente=5.0):
        raise Exception('Not implemented')

    async def clear(self):
        pass  # Optionnel

    async def run_display(self, feeds):
        while True:
            try:
                data_generator = feeds(name=self.__class__.__name__)
                
                # Maj duree affichage date (config)
                try:
                    self.__duree_afficher_datetime = data_generator.duree_date
                except AttributeError:
                    self.__duree_afficher_datetime = 10
                
                # Affichage heure
                await self.afficher_datetime()
                compteur = 0
                lignes = data_generator.generate(group=self._nb_lignes)
                if lignes is not None:
                    await self.clear()
                    for ligne, flag, duree in lignes:
                        compteur += 1
                        await self.preparer_ligne(ligne[:self._nb_chars], flag)
                        if compteur == self._nb_lignes:
                            compteur = 0
                            await self.show()
                            await self.clear()

                    if compteur > 0:
                        # Afficher la derniere page (incomplete)
                        for _ in range(compteur, self._nb_lignes):
                            await self.preparer_ligne('')
                        await self.show()
            
            except OSError as e:
                print("Display OSError")
                print_exception(e)
                # Attendre 30 secs avant de reessayer
                await asyncio.sleep(30)
    
    async def afficher_datetime(self):
        import time
        
        if self.__duree_afficher_datetime is None:
            return

        await self.clear()

        temps_limite = time.time() + self.__duree_afficher_datetime
        while temps_limite >= time.time():
            now = time.time()
            if self._appareil.timezone is not None:
                now += self._appareil.timezone
            (year, month, day, hour, minutes, seconds, _, _) = time.localtime(now)
            await self.preparer_ligne('{:d}-{:0>2d}-{:0>2d}'.format(year, month, day))
            await self.preparer_ligne('{:0>2d}:{:0>2d}:{:0>2d}'.format(hour, minutes, seconds))
            nouv_sec = (time.ticks_ms() % 1000) / 1000
            await self.show(nouv_sec)

    def get_display_params(self):
        return {
            'name': self.__class__.__name__,
            'format': 'text',
            'width': self._nb_chars,
            'height': self._nb_lignes,
        }


class DummyOutput(OutputLignes):
    
    #def __init__(self, appareil, params, busses, ui_lock):
    #    super().__init__(appareil, params, busses, ui_lock)
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock, 80, 8)
    
    def _get_instance(self):
        return None
    
    async def preparer_ligne(self, data, flag=None):
        print("DummyOutput: %s (%s)" % (data, flag))
        
    async def show(self, attente=5.0):
        await asyncio.sleep(attente)
        
