import time
import uasyncio as asyncio

from handler_programmes import ProgrammeActif
from millegrilles.config import get_tz_offset, get_horaire_solaire


JOUR_SECS = const(86400)
SLEEP_CHECK_SECS = const(30)


VALEURS_SOLAIRE = ['dawn', 'sunrise', 'noon', 'sunset', 'dusk']


class TransitionTimestampEffet:

    def __init__(self, etat: int, timestamp: int):
        self.etat = etat
        self.timestamp = timestamp

    def __eq__(self, other):
        return self.timestamp == other.timestamp and self.etat == other.etat

    def __lt__(self, other):
        if self.timestamp < other.timestamp:
            return True

        if self.timestamp == other.timestamp and self.etat < other.etat:
            return True

        return False

    def __str__(self):
        return 'TransitionTimestampEffet ts: {} etat => {}'.format(self.timestamp, self.etat)

    def __repr__(self):
        return self.__str__()


class HoraireMinuteEffet:
    """
    Transition vers un etat sur horaire pour heure:minute (jour optionnel).
    """
    
    def __init__(self, etat, heure=None, minute=None, jour=None, solaire=None):
        """
        @param etat: Valeur (0=OFF, 1=ON) a donner pour cette transition
        @param heure: Heure de la journee
        @param minute: Minute dans l'heure
        @param jour: Jour de la semaine. 0=dimanche/6=samedi
        @param solaire: Evenement solaire (dawn, sunrise, noon, sunset, dusk)
        """
        self.__etat = etat
        self.__heure = heure
        self.__minute = minute
        self.__jour = jour
        self.__solaire = solaire

    def appliquer(self, timezone_offset: int, config_solaire: dict = None, inverse=False) -> TransitionTimestampEffet:
        if timezone_offset is None:
            raise ValueError('tz offset manquant')

        timestamp_now = time.time()
        year_now, month_now, day_now, hour_now, minute_now, second_now, dow_now, yd_now = time.gmtime(timestamp_now)

        if self.__solaire:
            if config_solaire is None or config_solaire.get(self.__solaire) is None:
                print('Config solaire absente, skip')
                return None

            # Note : horaire solaire est exprime en heure/minute UTC
            hour, minute = config_solaire[self.__solaire]
            timestamp_horaire = time.mktime((year_now, month_now, day_now, hour, minute, 0, None, None))

            if isinstance(self.__minute, int):
                # Appliquer offset en minutes (e.g. dawn + 15 minutes)
                timestamp_horaire = timestamp_horaire + 60 * self.__minute

            if inverse:
                if timestamp_horaire > timestamp_now:
                    # Retirer le timestamp de 24h (evenement solaire precedent du meme type)
                    timestamp_horaire = timestamp_horaire - JOUR_SECS
            else:
                if timestamp_horaire < timestamp_now:
                    # Augmenter le timestamp de 24h (prochain evenement solaire du meme type)
                    timestamp_horaire = timestamp_horaire + JOUR_SECS

            print("evenement solaire %s -> %s" % (self.__solaire, timestamp_horaire))
        elif isinstance(self.__heure, int) and isinstance(self.__minute, int):
            # Appliquer heure et minute en fonction du timezone offset
            timestamp_horaire = time.mktime((year_now, month_now, day_now, self.__heure, self.__minute, 0, None, None))

            # Appliquer timezone offset
            # print("offset recu %s, appliquer a %s" % (timezone_offset, timestamp_horaire))
            timestamp_horaire = timestamp_horaire - timezone_offset # + offset_local

            if inverse:
                if timestamp_horaire > timestamp_now:
                    # Diminuer le timestamp de 24h (heure identique jour precedent)
                    timestamp_horaire -= JOUR_SECS
            else:
                if timestamp_horaire < timestamp_now:
                    # Augmenter le timestamp de 24h (prochaine heure identique)
                    timestamp_horaire += JOUR_SECS

            print("evenement heure %s:%s => %s" % (self.__heure, self.__minute, timestamp_horaire))
        else:
            raise ValueError("horaire vals incompatibles : %s" % self)

        if isinstance(self.__jour, str):
            # Jour desire
            jour_prog = int(self.__jour)
            # Jour courant - deja calcule
            # dow_now = time.gmtime(timestamp_horaire + timezone_offset)[6]

            # Trouver le prochain jour de la semaine correspondant
            diff_jours = jour_prog - dow_now
            if inverse is True:
                if diff_jours > 0:
                    # On a le nombre de jours a retirer (e.g. vendredi(4) - mardi(1) => 3, on veut -4 jours depuis le dernier vendredi
                    diff_jours = -1 * (7-diff_jours)
                elif diff_jours < 0:
                    # On a deja le nombre de jours depuis le dernier mardi : mardi(1) - vendredi(4) = -3,
                    pass
            elif inverse is False and diff_jours < 0:
                # Ajouter une semaine au nombre negatif, donne le nombre de jours a ajouter
                diff_jours += 7

            # print("Ajustement de %d jours" % diff_jours)
            timestamp_horaire += diff_jours * JOUR_SECS

            print("evenement wkday %s -> %s" % (self.__jour, timestamp_horaire))

        return TransitionTimestampEffet(self.__etat, timestamp_horaire)

    @property
    def etat(self):
        return self.__etat
    
    @property
    def heure(self):
        return self.__heure

    @property
    def minute(self):
        return self.__minute

    @property
    def jour(self):
        return self.__jour

    @property
    def solaire(self):
        return self.__solaire

    def __str__(self):
        return 'Horaire {}:{} jours ({}) solaire {} etat => {}'.format(
            self.__heure, self.__minute, self.__jour, self.__solaire, self.__etat)

    def __repr__(self):
        return self.__str__()


class HoraireHebdomadaire(ProgrammeActif):
    """
    Timer qui supporte une cedule sur 7 jours pour une/plusieurs switch.
    """
    
    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        # Liste de senseurs d'humidite par senseur_id
        self.__switches = list()

        # Liste des horaires
        # Format: [ {"etat": 1, "heure": 8, "minute": 15, "jours_semaine": [5]}, ... ] 
        self.__cedule: list[HoraireMinuteEffet] = list()

        self.__activation_initiale = False
        self.__premiere_execution_complete = False

        # Init apres, appelle charger_args() dans super
        super().__init__(appareil, programme_id, args, intervalle=60_000)

        self.__expiration_hold = None
        self.__prochaine_transition = None
        self.__tz: int = None

    def charger_args(self, args: dict):
        super().charger_args(args)
        self.__switches = args['switches']
        self.__cedule = self.__charger_cedule(args['horaire'])
        self.__activation_initiale = args.get('activationInitiale') or False
        print("Nouvelle cedule chargee pour %s : %s (activationInitiale: %s)" % (
            self._programme_id, self.__cedule, self.__activation_initiale))

    def __charger_cedule(self, cedule_args: list):
        cedule_horaire = list()

        for transition in cedule_args:
            cedule = HoraireMinuteEffet(
                transition['etat'],
                transition.get('heure'),
                transition.get('minute'),
                transition.get('jour'),
                transition.get('solaire')
            )
            cedule_horaire.append(cedule)

        # S'assurer de forcer un nouveau calcul de l'horaire
        self.__prochaine_transition = None

        return cedule_horaire
        
    async def loop(self):
        # Attendre que l'horloge interne soit prete (pour calculer horaire)
        await self._appareil.rtc_pret.wait()

        etat_desire = self.__verifier_etat_desire()
        print("TimerHebdomadaire %s etat desire %s" % (self.programme_id, etat_desire))
        self.__premiere_execution_complete = True  # On a calcule le premier etat desire

        changement = False
        if etat_desire is not None:
            # S'assurer que les switch sont dans le bon etat
            for switch_nom in self.__switches:
                switch_id = switch_nom.split('/')[0]
                try:
                    print("TimerHebdomadaire Modifier etat switch %s => %s" % (switch_id, etat_desire))
                    device = self._appareil.get_device(switch_id)
                    changement = changement or device.value != etat_desire
                    device.value = etat_desire
                except (AttributeError, KeyError):
                    print("Erreur acces switch %s, non trouvee" % switch_id)

        if changement is True:
            self._appareil.stale_event.set()

        if self.__prochaine_transition is not None:
            sleep_duration = (self.__prochaine_transition.timestamp - time.time()) * 1000
            if sleep_duration < self.intervalle:
                # Indiquer qu'on veut une action plus rapidement que la duree habituelle de sleep
                self.set_intervalle_onetime(sleep_duration)

    def __verifier_etat_desire(self):
        """ Determine si la valeur des senseurs justifie etat ON ou OFF. """
        if self.programme_actif is False:
            return None  # inactif

        # Par defaut, aucun changement
        nouvel_etat = None
        recalculer_transitions = False

        if self.__tz != self._appareil.timezone:
            print('Changement de timezone, on recalcule')
            recalculer_transitions = True
            self.__tz = self._appareil.timezone
        elif self.__prochaine_transition is None:
            recalculer_transitions = True
        else:
            # Verifier si on execute la transition
            if self.__prochaine_transition.timestamp <= time.time():
                print("Executer transition : %s" % self.__prochaine_transition.etat)
                # Conserver transition
                nouvel_etat = self.__prochaine_transition.etat
                recalculer_transitions = True

        if nouvel_etat is None and self.__activation_initiale and self.__premiere_execution_complete is False:
            print("Calculer etat init horaire")
            transition_precedente = self.__calculer_horaire(inverse=True)
            if transition_precedente:
                nouvel_etat = transition_precedente.etat
                print("etat init : %s" % nouvel_etat)

        if recalculer_transitions:
            # Calculer prochaine transition
            prochaine_transition = self.__calculer_horaire()
            if prochaine_transition:
                self.__prochaine_transition = prochaine_transition  # TransitionTimestampEffet(epoch_prochain_etat, horaire_prochain)
                print("TimerHebdomadaire Prochaine transition dans %s -> %s" % (
                    prochaine_transition.timestamp-time.time(), prochaine_transition.etat))
            else:
                print("TimerHebdomadaire Aucunes transitions pour prochaine journee")
                self.__prochaine_transition = None
        
        return nouvel_etat

    def __calculer_horaire(self, inverse=False) -> TransitionTimestampEffet:
        # Charger info timezone, solaire a partir du flash
        horaire_solaire = get_horaire_solaire()
        timezone_offset = self._appareil.timezone

        if timezone_offset is not None:
            print("calculer horaire offset %s" % timezone_offset)
            cedule_appliquee = [c.appliquer(timezone_offset, horaire_solaire, inverse) for c in self.__cedule]
            # Retirer entrees none (timezone ou solaire manquant)
            cedule_appliquee = [c for c in cedule_appliquee if c is not None]
            cedule_appliquee.sort()
            print("calculer_horaire cedule : %s" % cedule_appliquee)

            try:
                if inverse:
                    return cedule_appliquee.pop()  # Derniere valeur (plus recente transition)
                else:
                    return cedule_appliquee.pop(0)  # Premiere valeur (prochaine transition)
            except IndexError:
                return
        else:
            print("Timezone absent - skip programmes")
