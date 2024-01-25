# MilleGrilles RPi PICO Micropython installation offline

## Dependances

Packages Debian/Ubuntu
* cmake 
* gcc-arm-none-eabi 
* libnewlib-arm-none-eabi 
* build-essential

## Compiler outils

Note : utiliser un environnement offline en fonction du guide sous le projet millegrilles.instance.python/doc

Compiler le cross-compiler :

<pre>
cd ~/git
git clone /var/lib/git/millegrilles.rpipico.git
rm -r micropython
git clone /var/lib/git/micropython.git
cd micropython
make -C mpy-cross
</pre>

Il faut preparer les submodules manuellement avec /var/lib/git.

<pre>
cd micropython/lib/
git clone /var/lib/git/asf4
git clone /var/lib/git/axtls
git clone /var/lib/git/berkeley-db-1.xx
git clone /var/lib/git/btstack
git clone /var/lib/git/cyw43-driver
git clone /var/lib/git/fsp
git clone /var/lib/git/libffi
git clone /var/lib/git/libhydrogen
git clone /var/lib/git/lwip
git clone /var/lib/git/mbedtls
git clone /var/lib/git/micropython-lib
git clone /var/lib/git/mynewt-nimble
git clone /var/lib/git/nrfx
git clone /var/lib/git/nxp_driver
git clone /var/lib/git/pico-sdk
git clone /var/lib/git/protobuf-c
git clone /var/lib/git/stm32lib
git clone /var/lib/git/tinyusb

cd ..
make -C ports/rp2 BOARD=RPI_PICO_W submodules

cd ~/git/millegrilles.rpipico/oryx-embedded/
git clone /var/lib/git/oryx-embedded-common.git
git clone /var/lib/git/oryx-embedded-cyclonecrypto.git
rmdir common
rmdir cyclone_crypto/
mv oryx-embedded-common common
mv oryx-embedded-cyclonecrypto/ cyclone_crypto

cd ~/git/millegrilles.rpipico
</pre>

Ajouter l'usager au groupe dialout pour interagir avec le RPi
`sudo adduser $USER dialout`

Compiler le projet pour s'assurer que tout est correct.
`./build.sh`
