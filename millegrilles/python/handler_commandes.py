from config import set_configuration_display, set_timezone_offset

async def traiter_commande(appareil, commande: dict):
    print("Traiter : %s" % commande)
    action = commande['en-tete']['action']
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
