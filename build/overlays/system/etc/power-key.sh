#!/bin/sh
# FLSUN S1 Open Source Edition

EVENT=${1:-short-press}

TIMEOUT=3 # s
PIDFILE="/run/$(basename $0).pid"

short_press()
{
	logger -t $(basename $0) "[$$]: Power key short press..."
  
  	echo _PWR_KEY > /dev/pts/1
  	echo _PWR_KEY > /dev/pts/0
}

long_press()
{
	logger -t $(basename $0) "[$$]: Power key long press (${TIMEOUT}s)..."
	logger -t $(basename $0) "[$$]: Prepare to power off..."

	poweroff
}

logger -t $(basename $0) "[$$]: Received power key event: $@..."

case "$EVENT" in
	press)
		# Lock it
		exec 3<$0
		flock -x 3

		start-stop-daemon -K -q -p $PIDFILE || true
		start-stop-daemon -S -q -b -m -p $PIDFILE -x /bin/sh -- \
			-c "sleep $TIMEOUT; $0 long-press"

		# Unlock
		flock -u 3
		;;
	release)
		# Avoid race with press event
		sleep .5
		start-stop-daemon -K -q -p $PIDFILE && short_press
		;;
	short-press)
		short_press
		;;
	long-press)
		long_press
		;;
esac
