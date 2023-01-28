from config import set_configuration_display, set_timezone_offset, \
    set_configuration_display, sauvegarder_relais, sauvegarder_relais_liste, \
    get_user_id
from message_inscription import recevoir_certificat
from millegrilles.mgmessages import verifier_message


async def traiter_commande(appareil, commande: dict, info_certificat: dict):
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
    elif action == 'commandeAppareil':
        await recevoir_commande_appareil(appareil, commande, info_certificat)
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
        # appareil.set_timezone_offset(offset)
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

async def recevoir_commande_appareil(appareil, reponse, info_certificat):
    print("Info certificat : %s" % info_certificat)
    if info_certificat['user_id'] != get_user_id():
        print("Commande appareil - mauvais user_id")
        return
    
    print("Commande recue, user_id OK : %s" % reponse)
    commande_action = reponse['commande_action']
    
    if commande_action == 'setSwitchValue':
        await appareil_set_switch_value(appareil, reponse['senseur_id'], reponse['valeur'])
    else:
        print("recevoir_commande_appareil Commande inconnue : %s" % commande_action)

async def appareil_set_switch_value(appareil, senseur_id, value):
    print("appareil_set_switch_value %s -> %s" % (senseur_id, value))

    device_id = senseur_id.split('/')[0]
    device = appareil.get_device(device_id)
    print("Device trouve : %s" % device)
    device.value = value

