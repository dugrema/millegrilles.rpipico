set -e

DEST=~/pico
mkdir $DEST
cd ~

wget -O $DEST/pico_setup.sh https://raw.githubusercontent.com/raspberrypi/pico-setup/master/pico_setup.sh


chmod 775 $DEST/pico_setup.sh

$DEST/pico_setup.sh

