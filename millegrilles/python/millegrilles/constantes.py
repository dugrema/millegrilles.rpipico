from micropython import const

# Fichiers de configuration
CONST_PATH_FICHIER_DISPLAY = const('displays.json')
CONST_PATH_FICHIER_PROGRAMMES = const('programmes.json')
CONST_PATH_TIMEINFO = const('timeinfo')
CONST_PATH_TZOFFSET = const('tzoffset.json')
CONST_PATH_SOLAIRE = const('solaire.json')

CONST_PATH_USER = const('user.json')
CONST_PATH_USER_NEW = const('user.new.json')

CONST_PATH_RELAIS = const('relais.json')
CONST_PATH_RELAIS_NEW = const('relais.new.json')

CONST_PATH_WIFI = const('wifi.json')
CONST_PATH_WIFI_NEW = const('wifi.new.json')


# Modes operation
CONST_MODE_INIT = const(1)
CONST_MODE_RECUPERER_CA = const(2)
CONST_MODE_CHARGER_URL_RELAIS = const(3)
CONST_MODE_SIGNER_CERTIFICAT = const(4)
CONST_MODE_POLLING = const(99)

# Timeouts
CONST_HTTP_TIMEOUT_DEFAULT = const(60)

# Fichiers
CONST_READ_BINARY = const('rb')
CONST_WRITE_BINARY = const('wb')

# Champs generiques
CONST_UTF8 = const('utf-8')
CONST_CHAMP_HTTP_INSTANCE = const('http_instance')
CONST_CHAMP_HTTP_TIMEOUT = const('http_timeout')
CONST_CHAMP_WIFI_SSID = const('ssid')
CONST_CHAMP_WIFI_CHANNEL = const('channel')
CONST_CHAMP_IP = const('ip')
CONST_CHAMP_IDMG = const('idmg')
CONST_CHAMP_USER_ID = const('user_id')
CONST_CHAMP_TIMEZONE = const('timezone')
CONST_CHAMP_OFFSET = const('offset')
CONST_CHAMP_TRANSITION_TIME = const('transition_time')
CONST_CHAMP_TRANSITION_OFFSET = const('transition_offset')
CONST_CHAMP_PATHNAME = const('pathname')
CONST_CHAMP_PORTS = const('ports')
CONST_CHAMP_HTTPS = const('https')
CONST_CHAMP_DOMAINES = const('domaines')
CONST_CHAMP_RELAIS = const('relais')

# Champs fichie
CONST_CHAMP_APPLICATIONSV2 = const('applicationsV2')
CONST_CHAMP_SENSEURSPASSIFS_RELAI = const('senseurspassifs_relai')
CONST_CHAMP_INSTANCES = const('instances')

# Configuration solaire
CONST_CHAMPS_SOLAIRE = const(('dawn', 'sunrise', 'noon', 'sunset', 'dusk'))
CONST_SOLAIRE_CHANGEMENT = const(120)


CONST_SHORT_MIN = const(-32768)