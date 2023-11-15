import asyncio
import json

from binascii import unhexlify

from millegrilles.config import set_configuration_display, update_configuration_programmes, \
     set_timezone_offset, sauvegarder_relais, sauvegarder_relais_liste

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
            certificat = commande['certificat']
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
        offset = json.loads(commande['contenu'])['timezone_offset']
        print("Set offset recu : %s" % offset)
        # appareil.set_timezone_offset(offset)
        await set_timezone_offset(offset)
    except KeyError:
        print("offset absent du message")


async def recevoir_configuration_display(reponse):
    try:
        commande = json.loads(reponse['contenu'])
        displays = commande['display_configuration']['configuration']['displays']
        set_configuration_display(displays)
    except KeyError:
        print("Erreur reception displays %s" % reponse)


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
    chiffrage_messages = appareil.chiffrage_messages
    chiffrage_messages.clear()
