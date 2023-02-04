#!/bin/bash

REP_BASE=`pwd`
REP_RP2="${REP_BASE}/micropython/ports/esp32"
REP_MG_SRC="${REP_BASE}/millegrilles/src"
REP_MILLEGRILLES_PYTHON="${REP_BASE}/millegrilles/python"
REP_MILLEGRILLES_LIB="${REP_BASE}/millegrilles/lib"

export BOARD=GENERIC_D2WD
#export USER_C_MODULES="${REP_MG_SRC}/micropython.cmake"
export IDF_TARGET='esp32'

rm "${REP_BASE}/firmware.uf2"

# Preparer mpy PYTHON
cd "${REP_MILLEGRILLES_PYTHON}"
make clean; make all
cp -r "${REP_MILLEGRILLES_PYTHON}/build/millegrilles" "${REP_RP2}/modules/"

# Prepary mpy libs
cd "${REP_MILLEGRILLES_LIB}"
make clean; make all
cp -r ${REP_MILLEGRILLES_LIB}/build/* "${REP_RP2}/modules/"

# Move dans rep RP2
cd "$REP_RP2"

if [ -z $NOCLEAN ]; then
  echo "Cleaning project by default"
  make clean
fi
make

#cp "${REP_BASE}/micropython/ports/rp2/build-PICO_W/firmware.uf2" "${REP_BASE}"
