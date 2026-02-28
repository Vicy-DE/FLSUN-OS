#!/bin/bash
# FLSUN S1 Open Source Edition

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
NEW_HOSTNAME="FLSUN-S1-$MAC_SUFFIX"
hostnamectl set-hostname "$NEW_HOSTNAME"
sed -i "s/^127\.0\.1\.1\s.*/127.0.1.1\t$NEW_HOSTNAME/" /etc/hosts
echo "New hostname defined!"

echo "Reconfigure OpenSSH Server..."
ssh-keygen -A
systemctl restart ssh
echo "OpenSSH Server reconfigured!"

echo "Create symlink for FLSUN Installer..."
ln -sf /home/pi/flsun-os/installer/installer.sh /usr/bin/easy-installer
echo "Symlink for FLSUN Installer created!"

echo "Create symlink for Kiauh..."
ln -sf /home/pi/kiauh/kiauh.sh /usr/bin/kiauh
echo "Symlink for Kiauh created!"

echo "Applying Web-UI configurations..."
restoreJSON() {
    local jsonFile="$1"
    local baseUrl="$2/server/database/item"
	local namespace="$3"
    local namespaceUrl="${baseUrl}?namespace=${namespace}"
    local responseNamespaces=$(curl -s "$2/server/database/list")
    local namespacesArray=$(echo "$responseNamespaces" | jq -r '.result.namespaces[]')
    local existingArray=()
	
	printf "\r\n------ Restoring ${namespace} ------\r\n"
	
    if [[ " ${namespacesArray[@]} " =~ "${namespace}" ]]; then
        local responseNamespaceUrl=$(curl -s "$namespaceUrl")
        existingArray=($(echo "$responseNamespaceUrl" | jq -r '.result.value | keys[]'))
    fi
	
	if [[ "${namespace}" == "fluidd" ]]; then
		local keys=$(jq -r "keys[]" <<< "$(jq -r ".data" "$jsonFile")")
	else
		local keys=$(jq -r 'keys[]' "$jsonFile")
	fi
    
    for key in $keys; do
        if [[ "$key" == "timelapse" || "$key" == "webcams" ]]; then
            local subkeys=$(jq -r "keys[]" <<< "$(jq -r ".${key}" "$jsonFile" 2>/dev/null)" 2>/dev/null)
			if [ -n "$subkeys" ]; then
				if [[ " ${namespacesArray[@]} " =~ "$key" ]]; then
					local url="${baseUrl}?namespace=${key}"
					local response=$(curl -s "$url")
					local objects=$(echo "$response" | jq -r '.result.value | keys[]')
					for item in $objects; do
						printf "\r\ndelete ${key}.${item}\r\n"
						curl -s -X DELETE "${url}&key=${item}" > /dev/null
					done
				fi

				for key2 in $subkeys; do
					printf "add ${key}.${item}\r\n"
					local value=$(jq -r ".${key}[\"${key2}\"]" "$jsonFile")
					curl -s -X POST "$baseUrl" -H "Content-Type: application/json" -d "{\"namespace\":\"$key\",\"key\":\"$key2\",\"value\":$value}" > /dev/null
				done
			fi
        else
            if [[ " ${existingArray[@]} " =~ "$key" ]]; then
				printf "\r\ndelete ${key}\r\n"
                curl -s -X DELETE "${namespaceUrl}&key=${key}" > /dev/null
            fi
			printf "add ${key}\r\n"
			if [[ "${namespace}" == "fluidd" ]]; then
				local value=$(jq -r ".data.${key}" "$jsonFile")
			else
				local value=$(jq -r ".${key}" "$jsonFile")
			fi
            curl -s -X POST "$namespaceUrl" -H "Content-Type: application/json" -d "{\"namespace\":\"${namespace}\",\"key\":\"$key\",\"value\":$value}" > /dev/null
        fi
    done
}

restoreJSON "/home/pi/flsun-os/installer/files/Backup-Mainsail-FLSUN-S1.json" "http://127.0.0.1:7125" "mainsail"
restoreJSON "/home/pi/flsun-os/installer/files/Backup-Fluidd-FLSUN-S1.json" "http://127.0.0.1:7125" "fluidd"
systemctl restart moonraker
echo "Web-UI configurations applied!"

sed -i '/\/etc\/init.d\/first-boot.sh/d' /etc/rc.local

echo "Enabling zram swap..."
echo "/dev/zram0 none swap sw,pri=32767 0 0" | tee -a /etc/fstab
echo "zram swap enabled!"

echo "Rebooting system..."
sleep 5 && reboot &
