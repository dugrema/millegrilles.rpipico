import time
from handler_programmes import ProgrammeActif


TYPE_SENSEUR_HUMIDITE = const('humidite')
TYPE_SENSEUR_TEMPERATURE = const('temperature')
TYPE_SENSEUR_PRESSION_TENDANCE = const('pression_tendance')

INTERVALLE_EMISSION_DEFAUT = const(120)
INTERVALLE_REEMISSION_DEFAUT = const(3600)

class ProgrammeNotification(ProgrammeActif):

    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        # Liste de senseurs de temperature
        self._senseurs = None

        # ---
        # Parametres optionnels avec valeur par defaut

        # Valeur ciblee (moyenne des senseurs)
        self._valeur_cible = 0.0
        # +/- cette valeur de la cible declenche un changement
        self._precision = 1.0

        # Duree minimale entre deux emission (ON -> OFF -> ON)
        self.__intervalle_emission = INTERVALLE_EMISSION_DEFAUT

        # Intervalle (secondes) entre re-emission de la meme notification si l'etat ne change pas (ON ... ON)
        self.__intervalle_reemission = INTERVALLE_REEMISSION_DEFAUT

        # True si on doit presentement emettre des notifications
        self.__etat_notifier = False

        # Prochaine date d'emission de notification si changement rapide d'etat
        self.__prochaine_emission_notification = None

        # Conserver la date de re-emission de la notification si etat le justifie
        self.__prochaine_reemission_notification = None

        self.__message_notification = None
        self.__valeur_courante = None

        # Init apres, appelle charger_args() dans super
        super().__init__(appareil, programme_id, args, intervalle=15_000)

    def get_senseurs(self):
        """ @return Liste des senseurs. Utilise pour identifier deps externe. """
        if self.actif is True:
            return self._senseurs

    def get_type_senseur(self):
        """ @return Type de senseur (e.g. temperature, humidite, pression) """
        raise NotImplementedError()

    async def generer_message(self) -> dict:
        """
        Methode invoquee regulierement.
        :returns: Un message (dict) si approprie, sinon None.
        """
        if self.actif is False:
            return None

        print('!notif! generer_message')

        now = int(time.time())

        if self.__etat_notifier is False:
            # Aucune notification a emettre
            return None
        elif self.__prochaine_reemission_notification is not None:
            if self.__prochaine_reemission_notification > time.time():
                return None  # Aucune notification permise pour le moment
            else:
                # Expiration hold
                self.__prochaine_reemission_notification = None

        if self.__prochaine_emission_notification is not None and self.__prochaine_emission_notification > now:
            # Abort, ne pas emettre la notification
            return None

        self.__prochaine_emission_notification = now + self.__intervalle_emission
        self.__prochaine_reemission_notification = now + self.__intervalle_reemission

        print('!notif! message genere, valeur courante %s, message notif %s' % (self.__valeur_courante, self.__message_notification))
        if self.__message_notification is not None:
            message = self.__message_notification.format(**{'valeur': self.__valeur_courante})
        else:
            message = 'Notification'

        return {
            'programme_id': self.programme_id,
            'message': message
        }

    def reverse_state(self):
        """ @return True si on doit inverser les actions ON et OFF """
        return False

    def charger_args(self, args: dict):
        super().charger_args(args)
        self.__message_notification = args.get('message') or self.__message_notification
        print("Message notification : %s" % self.__message_notification)
        self._senseurs = args.get('senseurs') or self._senseurs
        self._valeur_cible = args.get('valeur') or self._valeur_cible
        self._precision = args.get('precision') or self._precision
        self.__intervalle_emission = args.get('intervalle_emission') or self.__intervalle_emission
        self.__intervalle_reemission = args.get('intervalle_reemission') or self.__intervalle_reemission
        print("Nouvelle config chargee pour %s : %s" % (self._programme_id, args))

    async def loop(self):
        etat_desire = self._verifier_etat_desire()
        print("%s etat desire %s" % (self.programme_id, etat_desire))

        if etat_desire is not None:
            # Declencher emission de la notification (au besoin)
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
            self.__valeur_courante = moyenne_valeur
            return moyenne_valeur

    def _verifier_etat_desire(self):
        """ Determine si la valeur des senseurs justifie etat ON (emettre notification) ou OFF (ne pas emettre). """

        valeur_courante = self._calculer_valeur_courante()

        print('!notif! prog_id %s valeur courante %s' % (self.programme_id, valeur_courante))

        if valeur_courante is not None:
            if valeur_courante < (self._valeur_cible - self._precision):
                # Valeur est inferieure
                if self.reverse_state() is True:
                    return self.action_notifier_off()
                else:
                    return self.action_notifier_on()
            elif valeur_courante > (self._valeur_cible + self._precision):
                # Valeur est superieure
                if self.reverse_state() is True:
                    return self.action_notifier_on()
                else:
                    return self.action_notifier_off()
            else:
                return None  # Etat desire est l'etat courant (aucun changement)

        # On n'a aucune valeur courante - valeur desiree est 0 (OFF) sans timer de blocage
        return 0

    def action_notifier_on(self):
        """
        Emettre la notification.
        """
        print('!notif! %s action_notifier_on' % self.programme_id)
        if self.__etat_notifier is False:
            self.__prochaine_reemission_notification = None
            self.__etat_notifier = True
        return 1  # Notification doit etre envoyee

    def action_notifier_off(self):
        """
        Arreter d'emettre la notification (etat OK)
        """
        print('!notif! %s action_notifier_off' % self.programme_id)
        self.__etat_notifier = False
        self.__prochaine_reemission_notification = None
        return 0  # Aucunes notifications a envoyer

    def stop(self):
        """
        Arreter thread et mettre toutes les switch a OFF.
        """
        print("!notif! stop %s" % self.programme_id)
        self.__etat_notifier = False
        self.__prochaine_emission_notification = None
        self.__prochaine_reemission_notification = None
        super().stop()


class NotificationHumidite(ProgrammeNotification):

    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id, args)

        # False => ON si humidite < cible
        # True => ON si humidite est > cible
        self.__reverse_state = False

    def charger_args(self, args: dict):
        super().charger_args(args)
        self._senseurs = args['senseurs_humidite']
        self._valeur_cible = args.get('valeur') or 45.0
        self.__reverse_state = args.get('reverse') is True or False

    def get_type_senseur(self):
        return TYPE_SENSEUR_HUMIDITE

    def reverse_state(self):
        return self.__reverse_state


class NotificationTemperature(ProgrammeNotification):

    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id, args)

        # False => ON si temperature < cible
        # True => ON si temperature est > cible
        self.__reverse_state = False

    def charger_args(self, args: dict):
        super().charger_args(args)
        self._valeur_cible = args['valeur']
        self.__reverse_state = args.get('reverse') is True or False

    def get_type_senseur(self):
        return TYPE_SENSEUR_TEMPERATURE

    def reverse_state(self):
        # Climatisation fonctionne a l'envers des autres programmes, ON si temperature est > cible
        return self.__reverse_state


class NotificationPressionTendance(ProgrammeNotification):

    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id, args)

        # False => ON si valeur < cible
        # True => ON si valeur est > cible
        self.__reverse_state = False

    def charger_args(self, args: dict):
        super().charger_args(args)
        self._valeur_cible = args['valeur']
        self.__reverse_state = args.get('reverse') is True or False

    def get_type_senseur(self):
        return TYPE_SENSEUR_PRESSION_TENDANCE

    def reverse_state(self):
        # Climatisation fonctionne a l'envers des autres programmes, ON si temperature est > cible
        return self.__reverse_state
