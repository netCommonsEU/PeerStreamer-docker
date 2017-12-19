#!/bin/sh

cd /peerstreamer/peerstreamer
./peerstreamer-ng -c /tmp/channels.db -s "iface=${PSNGIFACE}" > /dev/null 2>&1
