import uasyncio as asyncio
import time
from handler_programmes import ProgrammeActif


class Humidificateur(ProgrammeActif):
    
    def __init__(self, appareil, programme_id, args=dict()):
        """
        @param appareil: Appareil avec acces aux lectures, devices (switch)
        """
        super().__init__(appareil, programme_id)

        # Liste des switch d'humidificateur
        self.__senseurs_humidite = args['senseurs_humidite']
        # Liste de senseurs d'humidite par senseur_id
        self.__switches_humidificateurs = args['switches_humidificateurs']

        # ---
        # Parametres optionnels avec valeur par defaut

        # Pourcentage cible pour l'humidite
        self.__humidite_cible = args.get('humidite') or 45.0
        # +/- cette valeur de la cible declenche un changement
        self.__precision = args.get('precision') or 0.5
        # Duree d'activite (ON) minimale en secondes par declenchement
        self.__duree_on_min = args.get('duree_on_min') or 180
        # Duree minimale d'arret (OFF) en secondes par declenchement
        self.__duree_off_min = args.get('duree_off_min') or 120
 
        self.__expiration_hold = None

    async def run(self):
        while self._actif is True:
            await self.__executer_cycle()
            # Attendre prochaine verification
            await asyncio.sleep(5)
        
    async def __executer_cycle(self):
        etat_desire = self.__verifier_etat_desire()
        print("%s etat desire %s" % (self.programme_id, etat_desire))

        changement = False
        if etat_desire is not None:
            # S'assurer que les switch sont dans le bon etat
            for switch_nom in self.__switches_humidificateurs:
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
        
    def __verifier_etat_desire(self):
        """ Determine si la valeur des senseurs justifie etat ON ou OFF. """

        if self.__expiration_hold is not None:
            if self.__expiration_hold > time.time():
                return None  # Aucun changement permis pour le moment
            else:
                # Expiration hold
                self.__expiration_hold = None
        
        temps_expire = time.time() - 300
        valeur_totale = 0.0
        nombre_valeurs = 0
        
        for senseur in self.__senseurs_humidite:
            # Get senseur
            # print("Get lecture senseur : %s\n%s\n%s" % (
            #     senseur, self._appareil.lectures_courantes, self._appareil.lectures_externes))
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
            
            # print("Lecture %s" % lecture_senseur)
            
            try:
                # Verifier que le senseur a une lecture de type humidite
                if lecture_senseur['type'] != 'humidite':
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
            print("Moyenne valeur humidite : %s" % moyenne_valeur)
            if moyenne_valeur < (self.__humidite_cible - self.__precision):
                self.__expiration_hold = time.time() + self.__duree_on_min
                return 1  # Etat desire est ON
            elif moyenne_valeur > (self.__humidite_cible + self.__precision):
                self.__expiration_hold = time.time() + self.__duree_off_min
                return 0  # Etat desire est OFF
            else:
                return None  # Etat desire est l'etat courant (aucun changement)
        
        # On n'a aucune valeur courante - valeur desiree est 0 (OFF)
        return 0
        
