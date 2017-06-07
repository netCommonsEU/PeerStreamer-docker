#!/bin/bash

# For now we simply start psng-pyserf.py in background
python /peerstreamer/psng-pyserf.py -t psngc -a 127.0.0.1 -p 7373 \
    bg /tmp/channels.db > /dev/null 2>&1 &
