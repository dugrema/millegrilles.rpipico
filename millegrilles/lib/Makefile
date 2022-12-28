MPYCROSS = ../../micropython/mpy-cross/build/mpy-cross

SRC_PYTHON = \
    baseconv.mpy bmp180_rpi.mpy lcd_api.mpy logging.mpy morphys.mpy pico_i2c_lcd.mpy ssd1306.mpy

SRC_MULTIFORMATS = \
    multiformats/converters.mpy multiformats/multibase.mpy multiformats/multihash.mpy

SRC_UWEBSOCKETS = \
    uwebsockets/client.mpy uwebsockets/protocol.mpy

%.mpy: %.py
	$(MPYCROSS) -O1 -o build/$@ $<

build_folders:
	mkdir -p build/multiformats build/uwebsockets

python: $(SRC_PYTHON) ${SRC_MULTIFORMATS} ${SRC_UWEBSOCKETS}

build: build_folders python

all: build

clean:
	rm -r build/
