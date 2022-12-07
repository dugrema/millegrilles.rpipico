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
            wifi_ip = self.__appareil.lectures_courantes['rp2pico/wifi']['valeur_str']
        except KeyError:
            print("No wifi lectures")
            #from wifi import get_etat_wifi
            #wifi_ip = get_etat_wifi()['ip']
            wifi_ip = 'N/A'
        data_lignes = ['WIFI IP', wifi_ip]
        while len(data_lignes) > 0:
            yield data_lignes.pop(0)


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
        
        masque = ligne['masque']
        
        try:
            appareil_nom = None
            variable = ligne['variable']
            variable = variable.split(':')
            if len(variable) > 2:
                raise Exception('Variable incorrecte')
            elif len(variable) == 2:
                appareil_nom, variable = variable
            else:
                variable = variable.pop()

            print("Appareil %s, Variable %s" % (appareil_nom, variable))

            senseur = self._appareil.lectures_courantes[variable]
            print("Senseur %s" % senseur)
            try:
                valeur = senseur['valeur_str']
            except KeyError:
                valeur = senseur['valeur']
            
            masque = masque.format(valeur)

        except (KeyError, ValueError, AttributeError) as e:
            print("Erreur formattage - OK")
        except Exception as e:
            print("Erreur generique formattage")
            print_exception(e)
        
        return masque
