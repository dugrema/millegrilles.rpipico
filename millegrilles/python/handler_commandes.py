async def traiter_commande(commande: dict):
    print("Traiter : %s" % commande)
    action = commande['en-tete']['action']
    if action == 'challengeAppareil':
        await challenge_led_blink(commande)
    else:
        raise ValueError('Action inconnue : %s' % action)


async def challenge_led_blink(commande: dict):
    from ledblink import led_executer_sequence
    challenge = commande['challenge']
    await led_executer_sequence(challenge, executions=2)
