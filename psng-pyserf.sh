#!/bin/sh

python /peerstreamer/psng-pyserf/psng-pyserf.py -t psngc -a 127.0.0.1 -p 7373 \
    bg /tmp/channels.db > /dev/null 2>&1
