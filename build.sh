#!/bin/bash

REP_BASE=`pwd`
REP_RP2="${REP_BASE}/micropython/ports/rp2"
REP_MG_SRC="${REP_BASE}/millegrilles/src"

export BOARD=PICO_W
export USER_C_MODULES="${REP_MG_SRC}/micropython.cmake"

rm "${REP_BASE}/firmware.uf2"

cd "$REP_RP2"

if [ -z $NOCLEAN ]; then
  echo "Cleaning project by default"
  make clean
fi
make

cp "${REP_BASE}/micropython/ports/rp2/build-PICO_W/firmware.uf2" "${REP_BASE}"
