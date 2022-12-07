class FeedDisplay:
    
    def __init__(self, appareil):
        self.__appareil = appareil
    
    def generate(self):
        raise Exception('Not implemente')


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
            yield ligne['masque']

