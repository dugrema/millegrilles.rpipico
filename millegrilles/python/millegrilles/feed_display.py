from math import ceil
from sys import print_exception
from time import time
from devices.display import SkipRemainingLines

MSG_WIFI_OFFLINE = const('WIFI OFFLINE')

class FeedDisplay:
    
    def __init__(self, appareil):
        self._appareil = appareil

    def generate(self, group=None):
        if self._appareil.get_display_override() is not None:
            return self.afficher_override()
        else:
            return self._generate(group)
    
    def _generate(self, group=None):
        raise NotImplementedError()
    
    def afficher_override(self):
        print("Afficher override")
        lignes = self._appareil.get_display_override()
        for ligne in lignes:
            yield ligne, None, 30.0, False


class FeedDisplayDefault(FeedDisplay):

    def __init__(self, appareil):
        super().__init__(appareil)

    def _generate(self, group=None):
        try:
            wifi_ip = self._appareil.lectures_courantes['rp2picow/wifi']['valeur_str']
        except KeyError:
            print("No wifi lectures")
            #from wifi import get_etat_wifi
            #wifi_ip = get_etat_wifi()['ip']
            wifi_ip = 'N/A'
        
        ligne_mode = 'Mode: {:02d}'.format(self._appareil.mode_operation)
        
        data_lignes = ['WIFI IP', wifi_ip, ligne_mode]
        if self._appareil.wifi_ok is not True:
            data_lignes.append(MSG_WIFI_OFFLINE)

        # Afficher date/heure
        yield '', 'DT', 5.0, True
            
        while len(data_lignes) > 0:
            # Verifier si un override est present
            if self._appareil.get_display_override() is not None:
                raise SkipRemainingLines()
            
            yield data_lignes.pop(0), None, None, False



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

    def _generate(self, group=None):
        
        # Afficher date/heure
        yield None, 'DT', None, False
        
        try:
            lignes = self.__config['lignes']
        except KeyError:
            return None, None, None, False
        
        if group is None:
            # print('Display group None')
            if self._appareil.wifi_ok is not True:
                yield MSG_WIFI_OFFLINE, None, 5.0, True
            for ligne in lignes:
                # Verifier si un override est present
                if self._appareil.get_display_override() is not None:
                    raise SkipRemainingLines()

                yield self.formatter_ligne(ligne)
                
        else:
            # print('Display group %s' % group)
            if self._appareil.wifi_ok is not True:
                yield MSG_WIFI_OFFLINE, None, 5.0, True
                for _ in range(1, group):
                    yield '', None, None, False
            
            refresh = 1.0
            
            while len(lignes) > 0:
                lignes_courantes = lignes[:group]
                lignes = lignes[group:]
                print('Display lignes : %s' % lignes_courantes)
                try:
                    duree = max([l.get('duree') for l in lignes_courantes if l.get('duree') is not None])
                    reps = ceil(duree / refresh)
                    duree_override = refresh
                    print("Duree %s, reps %s, override %s" % (duree, reps, duree_override))
                except ValueError as e:
                    print("Display value error pour \n%s" % lignes_courantes)
                    print_exception(e)
                    reps = 1
                    duree_override = None
                for rep_no in range(0, reps):
                    no_clear = rep_no != reps - 1
                    for ligne in lignes_courantes:
                        yield self.formatter_ligne(
                            ligne, duree_override=duree_override, no_clear=no_clear)
                        
                        # Verifier si un override est present
                        if self._appareil.get_display_override() is not None:
                            raise SkipRemainingLines()

    def formatter_ligne(self, ligne, duree_override=None, no_clear=False):
        masque = ligne['masque']
        duree = duree_override or ligne.get('duree')
        flag = None
        
        try:
            appareil_nom = None
            variable = ligne['variable']
            if variable is None or variable == '':
                return masque, flag, duree, True
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

        return masque, flag, duree, no_clear

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
    
