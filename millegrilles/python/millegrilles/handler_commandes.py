import asyncio
import json

from binascii import unhexlify

from millegrilles.config import set_configuration_display, update_configuration_programmes, \
     set_timezone_offset, sauvegarder_relais, sauvegarder_relais_liste, set_horaire_solaire, get_timezone, \
     set_nom_appareil

from millegrilles.certificat import get_userid_local
from millegrilles.message_inscription import recevoir_certificat
from millegrilles.mgmessages import formatter_message


async def traiter_commande(buffer, websocket, appareil, commande: dict, info_certificat: dict):
    try:
        routage = commande['routage']
        action = routage['action']
    except (TypeError, KeyError):
        action = commande['attachements']['action']  # Correlation a la reponse d'action de requete
    
    if action == 'challengeAppareil':
        await challenge_led_blink(appareil, commande)
    elif action == 'evenementMajDisplays':
        try:
            set_configuration_display(json.loads(commande['contenu'])['displays'])
        except KeyError:
            print("Erreur reception maj displays")
    elif action == 'evenementMajProgrammes':
        try:
            programmes = json.loads(commande['contenu'])['programmes']
            await recevoir_configuration_programmes(appareil, programmes)
        except KeyError:
            print("evenementMajProgrammes Aucuns programmes recus")
    elif action == 'lectures_senseurs':
        appareil.recevoir_lectures_externes(json.loads(commande['contenu'])['lectures_senseurs'])
    elif action == 'timezoneInfo':
        await recevoir_timezone_offset(appareil, commande)
    elif action == 'getAppareilProgrammesConfiguration':
        try:
            programmes = json.loads(commande['contenu'])['programmes']['configuration']['programmes']
            await recevoir_configuration_programmes(appareil, programmes)
        except (KeyError, AttributeError):
            print("getAppareilProgrammesConfiguration Aucuns programmes recus")
    elif action == 'getAppareilDisplayConfiguration':
        # Reponse display
        await recevoir_configuration_display(commande)
    elif action == 'signerAppareil':
        try:
            certificat = json.loads(commande['contenu'])['certificat']
            await recevoir_certificat(certificat)
        except KeyError as e:
            print("Erreur reception certificat KeyError %s" % str(e))
    elif action == 'fichePublique':
        await recevoir_fiche_publique(json.loads(commande['contenu']))
    elif action == 'relaisWeb':
        await recevoir_relais_web(json.loads(commande['contenu']))
    elif action == 'commandeAppareil':
        await recevoir_commande_appareil(appareil, commande, info_certificat)
    elif action == 'echangerSecret':
        await recevoir_echanger_secret(buffer, websocket, appareil, commande, info_certificat)
    elif action == 'resetSecret':
        await recevoir_reset_secret(appareil)
    elif action == 'majConfigurationAppareil':
        await recevoir_maj_configuration_appareil(appareil, buffer, websocket, commande)
    else:
        raise ValueError('Action inconnue : %s' % action)
    
    print("Commande %s traitee" % action)


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
        reponse = json.loads(commande['contenu'])
        print("tz reponse %s" % reponse)
    except KeyError:
        print("offset contenu absent")
        return

    try:
        offset = reponse['timezone_offset']
        timezone = reponse.get('timezone')
        transition_time = reponse.get('transition_time')
        transition_offset = reponse.get('transition_offset')
        print("Set offset recu : %s, timezone: %s, transition: %s, next offset: %s" % (offset, timezone, transition_time, transition_offset))
        await set_timezone_offset(offset, timezone, transition_time, transition_offset)
    except KeyError:
        print("offset absent du message")

    try:
        solaire = reponse['solaire_utc']
        await set_horaire_solaire(solaire)
    except KeyError:
        print("solaire absent du message tz")


async def recevoir_configuration_display(reponse):
    try:
        commande = json.loads(reponse['contenu'])
        configuration = commande['display_configuration']['configuration']
    except KeyError:
        print('ERR recv reponse displays (contenu)')
        return

    await asyncio.sleep(0)  # Yield

    try:
        displays = configuration['displays']
        set_configuration_display(displays)
    except KeyError:
        print("Erreur reception displays %s" % reponse)

    await asyncio.sleep(0)  # Yield

    try:
        descriptif_appareil = configuration['descriptif']
        set_nom_appareil(descriptif_appareil)
    except KeyError:
        pass


async def recevoir_configuration_programmes(appareil, programmes):
    print("%d programmes recus, ids %s)" % (len(programmes), programmes.keys()))
    await update_configuration_programmes(programmes, appareil)


async def recevoir_fiche_publique(fiche):
    sauvegarder_relais(fiche)


async def recevoir_relais_web(reponse):
    try:
        relais = reponse['relais']
        print("recevoir_relais_web %s" % relais)
        sauvegarder_relais_liste(relais)
    except KeyError:
        print("Erreur reception relais web (relais manquant)")


async def recevoir_commande_appareil(appareil, reponse, info_certificat):
    print("Info certificat : %s" % info_certificat)
    # if info_certificat['user_id'] != get_user_id():
    #     print("Commande appareil - mauvais user_id")
    #     return

    commande = reponse['contenu']
    if isinstance(commande, str):
        commande = json.loads(commande)
    
    print("Commande recue, user_id OK : %s" % commande)
    commande_action = commande['commande_action']
    
    if commande_action == 'setSwitchValue':
        await appareil_set_switch_value(appareil, commande['senseur_id'], commande['valeur'])
    else:
        print("recevoir_commande_appareil Commande inconnue : %s" % commande_action)


async def appareil_set_switch_value(appareil, senseur_id, value):
    print("appareil_set_switch_value %s -> %s" % (senseur_id, value))

    device_id = senseur_id.split('/')[0]
    device = appareil.get_device(device_id)
    print("Device trouve : %s" % device)
    device.value = value
    appareil.trigger_stale_event()


async def recevoir_echanger_secret(buffer, websocket, appareil, reponse, info_certificat):
    print("recevoir_echanger_secret Info certificat : %s" % info_certificat)
    print("recevoir_echanger_secret reponse : %s" % reponse)

    contenu = json.loads(reponse['contenu'])
    fingerprint = info_certificat['fingerprint']

    chiffrage_messages = appareil.chiffrage_messages
    chiffrage_messages.calculer_secret_exchange(contenu['peer'])

    # Emettre un message de confirmation - sert de permission pour relayer l'etat non signe de l'appareil
    conf = {'fingerprint': fingerprint}
    message_inscription = await formatter_message(
        conf, kind=2, action='confirmerRelai', domaine='SenseursPassifs',
        buffer=buffer, ajouter_certificat=True)

    buffer.clear()
    json.dump(message_inscription, buffer)
    message_inscription = None
    await asyncio.sleep_ms(1)  # Yield

    websocket.send(buffer.get_data())


async def recevoir_reset_secret(appareil):
    print('reset secret')
    chiffrage_messages = appareil.chiffrage_messages
    chiffrage_messages.clear()


async def recevoir_maj_configuration_appareil(appareil, buffer, websocket, commande):
    try:
        reponse = json.loads(commande['contenu'])
        print("maj appareil event %s" % reponse)
    except KeyError:
        print("maj appareil contenu absent")
        return

    timezone = reponse.get('timezone')
    timezone_courant = get_timezone()
    if timezone == timezone_courant:
        return  # Identique, aucuns changements

    chiffrage_messages = appareil.chiffrage_messages

    if chiffrage_messages.pret is False:
        return  # Skip

    print("tz recu : %s, remplacer timezone courant : %s" % (timezone, timezone_courant))

    # Chiffrer le message
    requete = {'timezone': timezone}
    requete = await chiffrage_messages.chiffrer(requete)
    requete['routage'] = {'action': 'getTimezoneInfo'}

    buffer.set_text(json.dumps(requete))

    # Emettre requete
    websocket.send(buffer.get_data())
