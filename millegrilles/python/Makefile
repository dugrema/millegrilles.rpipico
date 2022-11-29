MPYCROSS = ../../micropython/mpy-cross/build/mpy-cross

SRC_PYTHON = \
    appareil_millegrille.mpy baseconv.mpy etat.mpy handler_commandes.mpy ledblink.mpy message_inscription.mpy \
    mgmessages.mpy mgthreads.mpy morphys.mpy polling_messages.mpy urequests2.mpy wifi.mpy

SRC_MULTIFORMATS = \
    multiformats/converters.mpy multiformats/multibase.mpy multiformats/multihash.mpy

%.mpy: %.py
	$(MPYCROSS) -o build/$@ $<

build_folders:
	mkdir -p build/multiformats

python: $(SRC_PYTHON) ${SRC_MULTIFORMATS}

build: build_folders python

all: build

clean:
	rm -r build/
