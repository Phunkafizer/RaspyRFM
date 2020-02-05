dtc -@ -I dts -O dtb -o raspyrfm.dtbo raspyrfm.dts
cp raspyrfm.dtbo /boot/overlays/
echo "Comment this line in /boot/config.txt"
echo "#dtparam=spi=on"
echo "Add this line to /boot/config.txt"
echo "dtoverlay=raspyrfm"


