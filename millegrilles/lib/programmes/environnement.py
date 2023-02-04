import time
from handler_programmes import ProgrammeActif

TYPE_SENSEUR_HUMIDITE = const('humidite')
TYPE_SENSEUR_TEMPERATURE = const('temperature')


class ProgrammeEnvironnement(ProgrammeActif):

    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        # Liste de senseurs de temperature
        self._senseurs = None
        # Liste des switch
        self._switches = None

        # ---
        # Parametres optionnels avec valeur par defaut

        # Pourcentage cible pour l'humidite
        self._valeur_cible = 45.0
        # +/- cette valeur de la cible declenche un changement
        self.__precision = 0.5
        # Duree d'activite (ON) minimale en secondes par declenchement
        self.__duree_on_min = 180
        # Duree minimale d'arret (OFF) en secondes par declenchement
        self.__duree_off_min = 120

        # Init apres, appelle charger_args() dans super
        super().__init__(appareil, programme_id, args, intervalle=60_000)
        self.__expiration_hold = None

    def get_type_senseur(self):
        """ @return Type de senseur (e.g. temperature, humidite, pression) """
        raise NotImplementedError()

    def reverse_state(self):
        """ @return True si on doit inverser les actions ON et OFF """
        return False

    def charger_args(self, args: dict):
        super().charger_args(args)
        self._senseurs = args.get('senseurs') or self._senseurs
        self._switches = args.get('switches') or self._switches
        self._valeur_cible = args.get('valeur') or self._valeur_cible
        self.__precision = args.get('precision') or self.__precision
        self.__duree_on_min = args.get('duree_on_min') or self.__duree_on_min
        self.__duree_off_min = args.get('duree_off_min') or self.__duree_off_min
        print("Nouvelle config chargee pour %s : %s" % (self._programme_id, args))

    async def loop(self):
        etat_desire = self._verifier_etat_desire()
        print("%s etat desire %s" % (self.programme_id, etat_desire))

        changement = False
        if etat_desire is not None:
            # S'assurer que les switch sont dans le bon etat
            for switch_nom in self._switches:
                switch_id = switch_nom.split('/')[0]
                try:
                    device = self._appareil.get_device(switch_id)
                    print("Modifier etat switch %s => %s" % (switch_id, etat_desire))
                    changement = changement or device.value != etat_desire
                    device.value = etat_desire
                except KeyError:
                    print("Erreur acces switch %s, non trouvee" % switch_id)

        if changement is True:
            self._appareil.stale_event.set()

    def _calculer_valeur_courante(self):
        temps_expire = time.time() - 300
        valeur_totale = 0.0
        nombre_valeurs = 0

        for senseur in self._senseurs:
            # Get senseur
            senseur_split = senseur.split(':')
            if len(senseur_split) == 1:
                try:
                    lecture_senseur = self._appareil.lectures_courantes[senseur]
                except KeyError:
                    print("Senseur %s inconnu" % senseur)
                    continue
            elif len(senseur_split) == 2:
                try:
                    lecture_senseur = self._appareil.lectures_externes[senseur_split[0]][senseur_split[1]]
                except KeyError:
                    print("Senseur externe %s inconnu" % senseur)
                    continue
            else:
                print("Nom senseur non supporte %s" % senseur)
                continue  # Skip

            try:
                # Verifier que le senseur a une lecture de type temperature
                if lecture_senseur['type'] != self.get_type_senseur():
                    print("Senseur mauvais type %s" % lecture_senseur['type'])
                    continue  # Skip

                # Verifier si la lecture est courante (< 5 minutes)
                if lecture_senseur['timestamp'] < temps_expire:
                    print("Senseur lecture expiree")
                    continue  # Skip
            except KeyError:
                print("Champ type/timestamp manquant dans lecture")
                continue  # Skip

            # Cumuler la valeur
            try:
                valeur_totale = valeur_totale + float(lecture_senseur['valeur'])
                nombre_valeurs = nombre_valeurs + 1
            except (ValueError, KeyError):
                print("Erreur valeur senseur %s, ignorer pour Humidite" % lecture_senseur)
                continue  # Ignorer

        if nombre_valeurs > 0:
            moyenne_valeur = valeur_totale / nombre_valeurs
            print("Moyenne valeur courante : %s" % moyenne_valeur)
            return moyenne_valeur

    def _verifier_etat_desire(self):
        """ Determine si la valeur des senseurs justifie etat ON ou OFF. """

        if self.__expiration_hold is not None:
            if self.__expiration_hold > time.time():
                return None  # Aucun changement permis pour le moment
            else:
                # Expiration hold
                self.__expiration_hold = None

        valeur_courante = self._calculer_valeur_courante()

        if valeur_courante is not None:
            if valeur_courante < (self._valeur_cible - self.__precision):
                # Valeur est inferieure
                if self.reverse_state() is True:
                    return self.set_etat_off()
                else:
                    return self.set_etat_on()
            elif valeur_courante > (self._valeur_cible + self.__precision):
                # Valeur est superieure
                if self.reverse_state() is True:
                    return self.set_etat_on()
                else:
                    return self.set_etat_off()
            else:
                return None  # Etat desire est l'etat courant (aucun changement)

        # On n'a aucune valeur courante - valeur desiree est 0 (OFF) sans timer de blocage
        return 0

    def set_etat_on(self):
        self.__expiration_hold = time.time() + self.__duree_on_min
        return 1  # Etat desire est ON

    def set_etat_off(self):
        self.__expiration_hold = time.time() + self.__duree_off_min
        return 0  # Etat desire est OFF


class Humidificateur(ProgrammeEnvironnement):
    
    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id, args)

    def charger_args(self, args: dict):
        super().charger_args(args)
        self._senseurs = args['senseurs_humidite']
        self._switches = args['switches_humidificateurs']
        self._valeur_cible = args.get('humidite') or self._valeur_cible

    def get_type_senseur(self):
        return TYPE_SENSEUR_HUMIDITE


class Chauffage(ProgrammeEnvironnement):

    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id, args)

    def charger_args(self, args: dict):
        super().charger_args(args)
        self._valeur_cible = args.get('temperature') or self._valeur_cible

    def get_type_senseur(self):
        return TYPE_SENSEUR_TEMPERATURE


class Climatisation(ProgrammeEnvironnement):

    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id, args)

    def charger_args(self, args: dict):
        super().charger_args(args)
        self._valeur_cible = args.get('temperature') or self._valeur_cible

    def get_type_senseur(self):
        return TYPE_SENSEUR_TEMPERATURE
