MPYCROSS = ../../micropython/mpy-cross/build/mpy-cross

SRC_PYTHON = \
    appareil_millegrille.mpy baseconv.mpy handler_commandes.mpy ledblink.mpy message_inscription.mpy \
    mgmessages.mpy polling_messages.mpy wifi.mpy handler_devices.mpy feed_display.mpy \
    morphys.mpy urequests2.mpy certificat.mpy config.mpy const_leds.mpy \
    bmp180_rpi.mpy lcd_api.mpy pico_i2c_lcd.mpy ssd1306.mpy


SRC_MULTIFORMATS = \
    multiformats/converters.mpy multiformats/multibase.mpy multiformats/multihash.mpy

%.mpy: %.py
	$(MPYCROSS) -O1 -o build/$@ $<

build_folders:
	mkdir -p build/multiformats

python: $(SRC_PYTHON) ${SRC_MULTIFORMATS}

build: build_folders python

all: build

clean:
	rm -r build/
