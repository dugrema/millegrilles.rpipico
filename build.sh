#!/bin/bash

REP_BASE=`pwd`

cd "${REP_BASE}/micropython/ports/rp2"

make clean BOARD=PICO_W
make BOARD=PICO_W

