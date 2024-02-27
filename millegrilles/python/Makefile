MPYCROSS = ../../micropython/mpy-cross/build/mpy-cross

# SRC_PYTHON = \
#     handler_commandes.mpy


SRC_MILLEGRILLES = \
    millegrilles/appareil_millegrille.mpy \
    millegrilles/mgbluetooth.mpy \
    millegrilles/certificat.mpy \
    millegrilles/config.mpy \
    millegrilles/const_leds.mpy \
    millegrilles/constantes.mpy \
    millegrilles/etat.mpy \
    millegrilles/feed_display.mpy \
    millegrilles/ledblink.mpy \
    millegrilles/message_inscription.mpy \
    millegrilles/handler_commandes.mpy \
    millegrilles/chiffrage.mpy \
    millegrilles/mgmessages.mpy \
    millegrilles/mgthreads.mpy \
    millegrilles/pins.mpy \
    millegrilles/uping.mpy \
    millegrilles/urequests2.mpy \
    millegrilles/websocket_messages.mpy \
    millegrilles/watchdog.mpy \
    millegrilles/webutils.mpy \
    millegrilles/version.mpy \
    millegrilles/wifi.mpy

%.mpy: %.py
	$(MPYCROSS) -O1 -o build/$@ $<

build_folders:
	mkdir -p build/millegrilles

# python: $(SRC_PYTHON) ${SRC_MILLEGRILLES}
python: ${SRC_MILLEGRILLES}

build: build_folders python

all: build

clean:
	rm -r build/
