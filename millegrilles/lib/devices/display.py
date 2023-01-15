import uasyncio as asyncio
from sys import print_exception

from handler_devices import Driver


class OutputLignes(Driver):

    def __init__(self, appareil, params, busses, ui_lock: asyncio.Event, nb_chars=16, nb_lignes=2,
                 duree_afficher_datetime=10):
        super().__init__(appareil, params, busses, ui_lock)
        self._instance = None
        self.__busses = busses
        self._nb_lignes = nb_lignes
        self._nb_chars = nb_chars
        self.__duree_afficher_datetime = duree_afficher_datetime
        self._generateur_override = None

    async def load(self):
        self._instance = self._get_instance()

        try:
            await self._instance.setup()
        except AttributeError:
            pass  # No async setup required

        await self.preparer_ligne(b"Initialisation")
        await self.show(attente=0.1)

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
                    duree_page = 1.0  # Minimum 1 seconde
                    clear_after = True
                    for ligne, flag, duree, no_clear in lignes:
                        compteur += 1
                        if no_clear:
                            clear_after = False  # Toggle clear
                        try:
                            duree_page = max(duree_page, duree)
                        except TypeError:
                            pass  # OK, default
                        await self.preparer_ligne(ligne[:self._nb_chars], flag)
                        if compteur == self._nb_lignes:
                            compteur = 0
                            await self.show(attente=duree_page)
                            if clear_after is True:
                                await self.clear()
                            clear_after = True  # Reset

                    if compteur > 0:
                        # Afficher la derniere page (incomplete)
                        for _ in range(compteur, self._nb_lignes):
                            await self.preparer_ligne('')
                        await self.show()

            except SkipRemainingLines:
                print("run_display SkipRemainingLines")
                await self.clear()
                await asyncio.sleep_ms(10)
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

        index_loop = 0
        temps_limite = time.time() + self.__duree_afficher_datetime
        while temps_limite >= time.time():
            now = time.time()
            if self._appareil.timezone is not None:
                now += self._appareil.timezone

            timenow = time.localtime(now)
            for noligne in range(0, self._nb_lignes):
                await self._preparer_ligne_datetime(timenow, noligne, index_loop)

            nouv_sec = (time.ticks_ms() % 1000) / 1000
            await self.show(nouv_sec)
            index_loop += 1

    async def _preparer_ligne_datetime(self, timenow, ligne: int, index_loop: int):
        if ligne >= self._nb_lignes:
            # Cet affichage ne peut pas affaire ce nombre de ligne en meme temps
            return

        (year, month, day, hour, minutes, seconds, _, _) = timenow
        if ligne == 0:
            await self.preparer_ligne('{:d}-{:0>2d}-{:0>2d}'.format(year, month, day))
        elif ligne == 1:
            await self.preparer_ligne('{:0>2d}:{:0>2d}:{:0>2d}'.format(hour, minutes, seconds))
        #elif ligne == 2:
        #    await self.preparer_ligne('Ligne 3')
        #elif ligne == 3:
        #    await self.preparer_ligne('Ligne 4')

    def get_display_params(self):
        return {
            'name': self.__class__.__name__,
            'format': 'text',
            'width': self._nb_chars,
            'height': self._nb_lignes,
        }


class DummyOutput(OutputLignes):

    # def __init__(self, appareil, params, busses, ui_lock):
    #    super().__init__(appareil, params, busses, ui_lock)
    def __init__(self, appareil, params, busses, ui_lock):
        super().__init__(appareil, params, busses, ui_lock, 80, 8)

    def _get_instance(self):
        return None

    async def preparer_ligne(self, data, flag=None):
        print("DummyOutput: %s (%s)" % (data, flag))

    async def show(self, attente=5.0):
        await asyncio.sleep(attente)


class SkipRemainingLines(Exception):
    pass

