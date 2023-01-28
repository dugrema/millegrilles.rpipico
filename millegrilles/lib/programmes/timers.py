import uasyncio as asyncio
import time
from handler_programmes import ProgrammeActif


JOUR_SECS = const(86400)
SLEEP_CHECK_SECS = const(300)


class HoraireMinuteEffet:
    """
    Transition vers un etat sur horaire pour heure:minute (jour optionnel).
    """
    
    def __init__(self, etat, heure, minute, jours_semaine=None):
        """
        @param etat: Valeur (0=OFF, 1=ON) a donner pour cette transition
        @param heure: Heure de la journee
        @param minute: Minute dans l'heure
        @param jour_semaine: Jour de la semaine. 0=lundi/6=dimanche
        """
        self.__etat = etat
        self.__heure = heure
        self.__minute = minute
        self.__jours = jours_semaine
        
    def __eq__(self, other):
        if self.__etat != other.__etat: return False
        if self.__heure != other.__heure: return False
        if self.__minute != other.__minute: return False
        if self.__jours != other.__jours: return False
        return True

    def __lt__(self, other):
        if self.__heure < other.__heure: return True
        elif self.__heure != other.__heure: return False
        
        if self.__minute < other.__minute: return True
        elif self.__minute != other.__minute: return False

        if self.__jour is not None or other.__jours is not None:
            if self.__jours is None: return True
            if other.__jours is None: return False
            if self.__jours < other.__jours: return True

        if self.__etat < other.__etat: return True
        
        return False
    
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
    def jours(self):
        return self.__jours

    def __str__(self):
        return 'Horaire {:02d}:{:02d} jours ({}) etat => {}'.format(
            self.__heure, self.__minute, self.__jours, self.__etat)

    def __repr__(self):
        return self.__str__()


class ProchaineTransition:
    
    def __init__(self, timestamp, transition):
        self.timestamp = timestamp
        self.transition = transition


class TimerHebdomadaire(ProgrammeActif):
    """
    Timer qui supporte une cedule sur 7 jours pour une/plusieurs switch.
    """
    
    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id)

        # Liste de senseurs d'humidite par senseur_id
        self.__switches = args['switches']

        # Liste des horaires
        # Format: [ {"etat": 1, "heure": 8, "minute": 15, "jours_semaine": [5]}, ... ] 
        self.__cedule = self.__charger_cedule(args['horaire'])
        
        self.__prochaine_transition = None
 
    async def run(self):
        while self._actif is True:
            await self.__executer_cycle()
            # Attendre prochaine verification
            sleep_duration = SLEEP_CHECK_SECS
            if self.__prochaine_transition is not None:
                sleep_duration = min(sleep_duration, self.__prochaine_transition.timestamp - time.time())
            await asyncio.sleep(sleep_duration)
        
    def __charger_cedule(self, cedule_args: list):
        cedule_transitions = list()

        for transition in cedule_args:
            cedule_transitions.append(HoraireMinuteEffet(
                transition['etat'],
                transition['heure'],
                transition['minute'],
                transition.get('jours_semaine')
            ))

        cedule_transitions.sort()
        
        return cedule_transitions
        
    async def __executer_cycle(self):
        etat_desire = self.__verifier_etat_desire()
        # print("%s etat desire %s" % (self.programme_id, etat_desire))
        
        if etat_desire is not None:
            # S'assurer que les switch sont dans le bon etat
            for switch_nom in self.__switches:
                switch_id = switch_nom.split('/')[0]
                try:
                    print("TimerHebdomadaire Modifier etat switch %s => %s" % (switch_id, etat_desire))
                    device = self._appareil.get_device(switch_id)
                    device.value = etat_desire
                except (AttributeError, KeyError):
                    print("Erreur acces switch %s, non trouvee" % switch_id)
        
    def __verifier_etat_desire(self):
        """ Determine si la valeur des senseurs justifie etat ON ou OFF. """

        # Par defaut, aucun changement
        nouvel_etat = None
        recalculer_transitions = False

        if self.__prochaine_transition is None:
            recalculer_transitions = True
        else:
            # Verifier si on execute la transition
            if self.__prochaine_transition.timestamp <= time.time():
                # print("Executer transition : %s" % self.__prochaine_transition.transition)
                # Conserver transition
                nouvel_etat = self.__prochaine_transition.transition.etat
                recalculer_transitions = True
        
        if recalculer_transitions:
            # Calculer prochaine transition
            horaire_precedant, horaire_prochain, epoch_prochain_etat = self.__calculer_horaire()
            if horaire_prochain:
                self.__prochaine_transition = ProchaineTransition(epoch_prochain_etat, horaire_prochain)
                print("TimerHebdomadaire Prochaine transition dans %s : %s" % (epoch_prochain_etat-time.time(), horaire_prochain))
            else:
                print("TimerHebdomadaire Aucunes transitions pour prochaine journee")
                self.__prochaine_transition = None
        
        return nouvel_etat

    def __calculer_horaire(self):
        temps_courant = time.time()
        
        # Parcourir la cedule sur 3 jours (-24h a + 48h)
        jours = [
            time.localtime(temps_courant - JOUR_SECS),
            time.localtime(temps_courant),
            time.localtime(temps_courant + JOUR_SECS)
        ]
        
        # Trouver l'etat actuel en fonction de l'heure et la prochaine transition
        horaire_precedant = None
        horaire_prochain = None
        epoch_prochain_etat = None
        
        for temps in jours:  # Faire -24h, jour courant puis +24h
            
            for horaire in self.__cedule:
                
                # Verifier si cet horaire depend du jour de la semaine ou non
                if horaire.jours is not None and temps[6] not in horaire.jours:
                    continue  # Mauvais jour de la semaine, skip
                
                # Charger temps epoch pour cet horaire
                tuple_temps_horaire = (
                    temps[0], temps[1], temps[2], horaire.heure, horaire.minute, 0, None, None)
                horaire_secs = time.mktime(tuple_temps_horaire)
                
                if horaire_secs > temps_courant:
                    # C'est le prochain etat
                    epoch_prochain_etat = horaire_secs
                    horaire_prochain = horaire
                    break
                
                # Conserver horaire candidat
                horaire_precedant = horaire
            
            if horaire_prochain is not None:
                break        
    
        return horaire_precedant, horaire_prochain, epoch_prochain_etat
    
    