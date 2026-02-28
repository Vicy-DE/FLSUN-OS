#!/bin/bash
# FLSUN T1 Open Source Edition — First Boot Script
# Runs once on initial boot, then removes itself from rc.local

echo "Resizing rootfs..."
ROOT_PARTITION=$(findmnt -n -o SOURCE /)
DEVICE=$(lsblk -no pkname $ROOT_PARTITION)
PARTITION_NUMBER=$(echo $ROOT_PARTITION | grep -o '[0-9]*$')
sgdisk -e /dev/$DEVICE
parted /dev/$DEVICE resizepart $PARTITION_NUMBER 100%
resize2fs -f $ROOT_PARTITION
echo "rootfs resizing done!"

echo "Define new hostname..."
INTERFACE="wlan0"
MAC_SUFFIX=$(ip link show $INTERFACE | awk '/link\/ether/ {print $2}' | tr 'a-f' 'A-F' | sed 's/://g' | tail -c 5)
NEW_HOSTNAME="FLSUN-T1-$MAC_SUFFIX"
hostnamectl set-hostname "$NEW_HOSTNAME"
sed -i "s/^127\.0\.1\.1\s.*/127.0.1.1\t$NEW_HOSTNAME/" /etc/hosts
echo "New hostname defined!"

echo "Reconfigure OpenSSH Server..."
ssh-keygen -A
systemctl restart ssh
echo "OpenSSH Server reconfigured!"

echo "Create symlink for Kiauh..."
ln -sf /home/pi/kiauh/kiauh.sh /usr/bin/kiauh
echo "Symlink for Kiauh created!"

# Remove this script from rc.local so it doesn't run again
sed -i '/\/etc\/init.d\/first-boot.sh/d' /etc/rc.local

echo "Enabling zram swap..."
echo "/dev/zram0 none swap sw,pri=32767 0 0" | tee -a /etc/fstab
echo "zram swap enabled!"

echo "Rebooting system..."
sleep 5 && reboot &
