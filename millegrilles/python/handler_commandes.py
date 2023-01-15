from config import set_configuration_display, set_timezone_offset, \
    set_configuration_display, sauvegarder_relais, sauvegarder_relais_liste
from message_inscription import recevoir_certificat
from millegrilles.mgmessages import verifier_message


async def traiter_commande(appareil, commande: dict):
    try:
        action = commande['en-tete']['action']
    except KeyError:
        action = commande['_action']  # Correlation a la reponse d'action de requete
        
    if action == 'challengeAppareil':
        await challenge_led_blink(appareil, commande)
    elif action == 'evenementMajDisplays':
        try:
            set_configuration_display(commande['displays'])
        except KeyError:
            print("Erreur reception maj displays")
    elif action == 'lectures_senseurs':
        appareil.recevoir_lectures_externes(commande['lectures_senseurs'])
    elif action == 'timezoneInfo':
        await recevoir_timezone_offset(appareil, commande)
    elif action == 'getAppareilDisplayConfiguration':
        # Reponse display
        await recevoir_configuration_display(commande)
    elif action == 'signerAppareil':
        try:
            certificat = commande['certificat']
            await recevoir_certificat(certificat)
        except KeyError as e:
            print("Erreur reception certificat KeyError %s" % str(e))
    elif action == 'fichePublique':
        await recevoir_fiche_publique(commande)
    elif action == 'relaisWeb':
        await recevoir_relais_web(commande)
    else:
        raise ValueError('Action inconnue : %s' % action)


async def challenge_led_blink(appareil, commande: dict):
    from ledblink import led_executer_sequence
    challenge = commande['challenge']
    
    display = [
        'Activation',
        'Code: %s' % ','.join(challenge)
    ]
    appareil.set_display_override(display, duree=20)
    
    await led_executer_sequence(challenge, executions=2)


async def recevoir_timezone_offset(appareil, commande):
    try:
        offset = commande['timezone_offset']
        print("Set offset recu : %s" % offset)
        appareil.set_timezone_offset(offset)
        await set_timezone_offset(offset)
    except KeyError:
        print("offset absent du message")


async def recevoir_configuration_display(reponse):
    try:
        displays = reponse['display_configuration']['configuration']['displays']
        set_configuration_display(displays)
    except KeyError:
        print("Erreur reception displays %s" % reponse)

async def recevoir_fiche_publique(fiche):
    sauvegarder_relais(fiche)

async def recevoir_relais_web(reponse):
    try:
        sauvegarder_relais_liste(reponse['relais'])
    except KeyError:
        print("Erreur reception relais web (relais manquant)")
