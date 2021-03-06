#!/bin/bash
# load modules needed by anaconda
ARCH=$(uname -m)
KERNEL=$(uname -r)

MODULE_LIST="cramfs squashfs iscsi_tcp "

SCSI_MODULES=/lib/modules/$KERNEL/kernel/drivers/scsi/device_handler/
for m in $SCSI_MODULES/*.ko; do
    MODULE_LIST+=" `basename $m .ko` "
done

if [ "$ARCH" != "s390" -a "$ARCH" != "s390x" ]; then
    MODULE_LIST+=" floppy edd iscsi_ibft "
fi

if [ "$ARCH" = "ppc" ]; then
    MODULE_LIST+=" spufs "
fi

MODULE_LIST+=" raid0 raid1 raid5 raid6 raid456 raid10 linear dm-mod dm-zero  \
              dm-mirror dm-snapshot dm-multipath dm-round-robin dm-crypt cbc \
              sha256 lrw xts "

for m in $MODULE_LIST; do
    modprobe $m
done

