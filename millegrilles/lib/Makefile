MPYCROSS = ../../micropython/mpy-cross/build/mpy-cross

SRC_PYTHON = \
    baseconv.mpy \
    bmp180_rpi.mpy \
    lcd_api.mpy \
    logging.mpy \
    morphys.mpy \
    pico_i2c_lcd.mpy \
    ssd1306.mpy \
    handler_devices.mpy \
    handler_programmes.mpy

SRC_MULTIFORMATS = \
    multiformats/converters.mpy multiformats/multibase.mpy multiformats/multihash.mpy

SRC_UWEBSOCKETS = \
    uwebsockets/client.mpy uwebsockets/protocol.mpy

SRC_DEVICES = \
    devices/bmp.mpy \
    devices/bus.mpy \
    devices/dht.mpy \
    devices/display.mpy \
    devices/lcd1602.mpy \
    devices/onewire.mpy \
    devices/rpipico.mpy \
    devices/ssd1306.mpy \
    devices/switch.mpy

SRC_PROGRAMMES = \
    programmes/environnement.mpy \
    programmes/timers.mpy


%.mpy: %.py
	$(MPYCROSS) -O0 -o build/$@ $<

build_folders:
	mkdir -p build/multiformats build/uwebsockets build/devices build/programmes

python: $(SRC_PYTHON) ${SRC_MULTIFORMATS} ${SRC_UWEBSOCKETS} ${SRC_DEVICES} ${SRC_PROGRAMMES}

build: build_folders python

all: build

clean:
	rm -r build/
