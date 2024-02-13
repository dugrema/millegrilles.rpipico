#!/bin/bash

REP_BASE=`pwd`
REP_BUILD="${REP_BASE}/build"
REP_RP2="${REP_BASE}/micropython/ports/rp2"
REP_MG_SRC="${REP_BASE}/millegrilles/src"
REP_MILLEGRILLES_PYTHON="${REP_BASE}/millegrilles/python"
REP_MILLEGRILLES_LIB="${REP_BASE}/millegrilles/lib"

export BOARD=RPI_PICO_W
export USER_C_MODULES="${REP_MG_SRC}/micropython.cmake"

mkdir -p build
rm "${REP_BUILD}/firmware.uf2"

# Preparer mpy PYTHON
#echo "MILLEGRILLES_VERSION=const('2024.0.5')" > ${REP_MILLEGRILLES_PYTHON}/millegrilles/version.py
rm -r "${REP_RP2}/modules/millegrilles" || true
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

cp "${REP_BASE}/micropython/ports/rp2/build-${BOARD}/firmware.uf2" "${REP_BUILD}"
