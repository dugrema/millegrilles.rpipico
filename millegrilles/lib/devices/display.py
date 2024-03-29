import time

from micropython import const
from sys import print_exception

import uasyncio as asyncio

from handler_devices import Driver

CONST_NOT_IMPLEMENTED = const('Not implemented')
CONST_INITIALISATION = const(b'Initialisation')


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

        await self.preparer_ligne(CONST_INITIALISATION)
        await self.show(attente=0.1)

    def _get_instance(self):
        raise Exception(CONST_NOT_IMPLEMENTED)

    async def preparer_ligne(self, data, flag=None):
        raise Exception(CONST_NOT_IMPLEMENTED)

    async def show(self, attente=5.0):
        raise Exception(CONST_NOT_IMPLEMENTED)

    async def clear(self):
        pass  # Optionnel

    async def run_device(self, feeds):
        while True:
            try:
                data_generator = feeds(name=self.__class__.__name__)

                # Maj duree affichage date (config)
                try:
                    self.__duree_afficher_datetime = data_generator.duree_date
                except AttributeError:
                    self.__duree_afficher_datetime = 10

                compteur = 0
                lignes = data_generator.generate(group=self._nb_lignes)
                if lignes is not None:
                    await self.clear()
                    duree_page = 0.5  # Minimum 0.5 seconde
                    clear_after = True
                    temps_debut_rendering = time.time()

                    for ligne, flag, duree_ligne, no_clear in lignes:

                        if flag == 'DT':
                            # Afficher date/heure
                            await self.afficher_datetime()
                            continue
                        elif flag == 'PB':  # Page Break
                            if compteur == 0:
                                # Page Break, aucunes lignes
                                continue
                        elif flag == 'CL':  # Clear screen
                            await self.clear()
                            continue

                        compteur += 1
                        if no_clear:
                            clear_after = False  # Toggle clear
                        try:
                            duree_page = max(0.5, duree_page, duree_ligne)
                        except TypeError:
                            pass  # OK, default

                        if flag != 'PB':
                            await self.preparer_ligne(ligne[:self._nb_chars], flag)

                        if flag == 'PB' or compteur == self._nb_lignes:
                            compteur = 0
                            duree_page = max(0.5, temps_debut_rendering + duree_page - time.time())
                            await self.show(attente=duree_page)
                            if clear_after is True and duree_page > 0.5:
                                await self.clear()
                            duree_page = 0.5
                            clear_after = True  # Reset
                            temps_debut_rendering = time.time()  # Reset temps pour page

                    if compteur > 0:
                        duree_page = max(0.5, temps_debut_rendering + duree_page - time.time())
                        # Afficher la derniere page (incomplete)
                        for _ in range(compteur, self._nb_lignes):
                            await self.preparer_ligne('')
                        await self.show(attente=duree_page)

            except SkipRemainingLines:
                print(const("run_device SkipRemainingLines"))
                await self.clear()
                await asyncio.sleep_ms(10)
            except OSError as e:
                print(const("Display OSError"))
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
            # Attendre jusqu'a la nouvelle sec -50ms
            await self.show(nouv_sec-0.05)
            index_loop += 1

            # Boucler tant qu'on ne change pas de seconde
            while now == time.time():
                await asyncio.sleep_ms(100)

    async def _preparer_ligne_datetime(self, timenow, ligne: int, index_loop: int):
        if ligne >= self._nb_lignes:
            # Cet affichage ne peut pas affaire ce nombre de ligne en meme temps
            return

        (year, month, day, hour, minutes, seconds, _, _) = timenow
        if ligne == 0:
            await self.preparer_ligne(const('{:d}-{:0>2d}-{:0>2d}').format(year, month, day))
        elif ligne == 1:
            await self.preparer_ligne(const('{:0>2d}:{:0>2d}:{:0>2d}').format(hour, minutes, seconds))
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

