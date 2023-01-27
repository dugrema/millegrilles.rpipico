import uasyncio as asyncio
from programmes import ProgrammeActif

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
    
    async def run(self):
        while self._actif is True:
            await self.__executer_cycle()
            # Attendre prochaine verification
            await asyncio.sleep(5)
        
    async def __executer_cycle(self):
        etat_desire = self.__verifier_etat_desire()
        print("%s etat desire %s" % (self.programme_id, etat_desire))
        
    def __verifier_etat_desire(self):
        """ Determine si la valeur des senseurs justifie etat ON ou OFF. """
        lectures_courantes = self._appareil.lectures_courantes
        
        valeur_totale = 0.0
        nombre_valeurs = 0
        
        for senseur in self.__senseurs_humidite:
            # Get senseur
            
            # Verifier que le senseur a une lecture de type humidite
            
            # Verifier si la lecture est courante (< 5 minutes)
            
            # Cumuler la valeur
            
            pass
            
        if nombre_valeurs > 0:
            moyenne_valeur = valeur_totale / nombre_valeurs
            if moyenne_valeur < (self.__humidite_cible - self.__precision):
                return 1  # Etat desire est ON
            elif moyenne_valeur > (self.__humidite_cible + self.__precision):
                return 0  # Etat desire est OFF
            else:
                return None  # Etat desire est l'etat courant (aucun changement)
        
        # On n'a aucune valeur courante - valeur desiree est 0 (OFF)
        return 0
        
