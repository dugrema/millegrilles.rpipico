#!/bin/bash

REP_BASE=`pwd`
REP_RP2="${REP_BASE}/micropython/ports/rp2"

export BOARD=PICO_W

rm "${REP_BASE}/firmware.uf2"

cd "$REP_RP2"

make clean
make

#make clean BOARD=${BOARD}
#make BOARD=${BOARD}

cp "${REP_BASE}/micropython/ports/rp2/build-PICO_W/firmware.uf2" "${REP_BASE}"
