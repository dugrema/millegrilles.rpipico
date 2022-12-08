class FeedDisplay:
    
    def __init__(self, appareil):
        self._appareil = appareil
    
    def generate(self):
        raise Exception('Not implemented')


class FeedDisplayDefault(FeedDisplay):

    def __init__(self, appareil):
        super().__init__(appareil)

    def generate(self):
        try:
            wifi_ip = self._appareil.lectures_courantes['rp2pico/wifi']['valeur_str']
        except KeyError:
            print("No wifi lectures")
            #from wifi import get_etat_wifi
            #wifi_ip = get_etat_wifi()['ip']
            wifi_ip = 'N/A'
        
        ligne_mode = 'Mode: {:02d}'.format(self._appareil.mode_operation)
        
        data_lignes = ['WIFI IP', wifi_ip, ligne_mode]
        while len(data_lignes) > 0:
            yield data_lignes.pop(0), None


class FeedDisplayCustom(FeedDisplay):
    
    def __init__(self, appareil, display, config):
        super().__init__(appareil)
        self.__display = display
        self.__config = config
    
    @property
    def duree_date(self):
        try:
            return self.__config['afficher_date_duree']
        except KeyError:
            return None

    def generate(self):
        try:
            lignes = self.__config['lignes']
        except KeyError:
            return
        
        for ligne in lignes:
            yield self.formatter_ligne(ligne)

    def formatter_ligne(self, ligne):
        from sys import print_exception
        from time import time
        
        masque = ligne['masque']
        flag = None
        
        try:
            appareil_nom = None
            variable = ligne['variable']
            if variable is None or variable == '':
                return masque, flag
        except KeyError:
            pass
        else:
            try:
                valeur, timestamp_lecture = self.get_valeur(variable)
                if timestamp_lecture is not None:
                    temps_courant = time()
                    if temps_courant - timestamp_lecture > 1800:
                        flag = '!'
                    elif temps_courant - timestamp_lecture > 300:
                        flag = '?'
                masque = masque.format(valeur)
            except (KeyError, ValueError, AttributeError) as e:
                # print("Erreur formattage")
                # print_exception(e)
                try:
                    masque = masque.format(0)
                    masque = masque.replace('.0', '').replace('0', 'N/D')
                except:
                    pass
                # Valeur manquante
            except Exception as e:
                print("Erreur generique formattage")
                print_exception(e)

        return masque, flag

    def get_valeur(self, senseur_nom: str):
        senseur_nom = senseur_nom.split(':')

        if len(senseur_nom) > 2:
            raise Exception('Nom senseur incorrect : %s' % senseur_nom)
        elif len(senseur_nom) == 2:
            uuid_appareil, senseur_nom = senseur_nom
        else:
            uuid_appareil = None
            senseur_nom = senseur_nom.pop()

        if uuid_appareil is not None:
            # print("Appareil externe : %s, senseur %s" % (uuid_appareil, senseur_nom))
            # print("Lectures externes : %s" % self._appareil.lectures_externes)
            senseur = self._appareil.lectures_externes[uuid_appareil][senseur_nom]
            # print("Senseur externe trouve : %s" % senseur)
        else:
            senseur = self._appareil.lectures_courantes[senseur_nom]

        try:
            timestamp_lecture = senseur['timestamp']
        except KeyError:
            timestamp_lecture = None

        try:
            return senseur['valeur_str'], timestamp_lecture
        except KeyError:
            return senseur['valeur'], timestamp_lecture
    
