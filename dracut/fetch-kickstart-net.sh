#!/bin/bash
# fetch-kickstart-net - fetch kickstart file from the network.
# runs from the "initqueue/online" hook whenever a net interface comes online

# we already processed the kickstart - exit
[ -e /tmp/ks.cfg.done ] && return 0

# no kickstart requested - exit
[ -n "$kickstart" ] || return 0

# user requested a specific device, but this isn't it - exit
[ -n "$ksdevice" ] && [ "$ksdevice" != "$netif" ] && return 0

# no ksdevice was requested, so the first device online wins!
[ -z "$ksdevice" ] && ksdevice="$netif"

command -v getarg >/dev/null || . /lib/dracut-lib.sh
. /lib/url-lib.sh
. /lib/anaconda-lib.sh

if [ "$kickstart" = "nfs:auto" ]; then
    # construct kickstart URL from dhcp info
    # server is next_server, or the dhcp server itself if missing
    . /tmp/net.$netif.dhcpopts
    server="${new_dhcp_next_server:-$new_dhcp_server_identifier}"
    # filename is dhcp 'filename' option, or '/kickstart/' if missing
    filename="/kickstart/"
    # read the dhcp lease file and see if we can find 'filename'
    { while read line; do
        val="${line#filename }"
        if [ "$val" != "$line" ]; then
            eval "filename=$val" # drop quoting and semicolon
        fi
      done
    } < /tmp/net.$netif.lease
    # filename is appended with '$IP_ADDR-kickstart' if ending in '/'
    if [ "${filename%/}" != "$filename" ]; then
        filename="${filename}${new_ip_address}-kickstart"
    fi
    kickstart="nfs:$server:$filename"
fi

info "anaconda fetching kickstart from $kickstart"
if fetch_url "$kickstart" /tmp/ks.cfg; then
    parse_kickstart /tmp/ks.cfg
    run_kickstart
else
    warn "failed to fetch kickstart from $kickstart"
fi
