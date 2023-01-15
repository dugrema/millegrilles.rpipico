from config import set_configuration_display, set_timezone_offset, \
    set_configuration_display, sauvegarder_relais
from message_inscription import recevoir_certificat
from millegrilles.mgmessages import verifier_message


async def traiter_commande(appareil, commande: dict):
    # print("Traiter : %s" % commande['en-tete'])
    try:
        action = commande['en-tete']['action']
    except KeyError:
        action = commande['_action']  # Correlation a la reponse d'action de requete
        
    if action == 'challengeAppareil':
        await challenge_led_blink(commande)
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
    else:
        raise ValueError('Action inconnue : %s' % action)


async def challenge_led_blink(commande: dict):
    from ledblink import led_executer_sequence
    challenge = commande['challenge']
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
    #info_cert = await verifier_message(fiche)
    #if 'core' in info_cert['roles']:
    #    sauvegarder_relais(fiche)
    sauvegarder_relais(fiche)
