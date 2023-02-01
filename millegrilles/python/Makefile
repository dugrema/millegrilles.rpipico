MPYCROSS = ../../micropython/mpy-cross/build/mpy-cross

SRC_PYTHON = \
    appareil_millegrille.mpy \
    config.mpy \
    feed_display.mpy \
    handler_commandes.mpy \
    message_inscription.mpy \
    websocket_messages.mpy


SRC_MILLEGRILLES = \
    millegrilles/appareil_millegrille.mpy \
    millegrilles/config.mpy \
    millegrilles/const_leds.mpy \
    millegrilles/etat.mpy \
    millegrilles/feed_display.mpy \
    millegrilles/ledblink.mpy \
    millegrilles/mgmessages.mpy \
    millegrilles/mgthreads.mpy \
    millegrilles/uping.mpy \
    millegrilles/urequests2.mpy \
    millegrilles/wifi.mpy

%.mpy: %.py
	$(MPYCROSS) -O1 -o build/$@ $<

build_folders:
	mkdir -p build/millegrilles

python: $(SRC_PYTHON) ${SRC_MILLEGRILLES}

build: build_folders python

all: build

clean:
	rm -r build/
