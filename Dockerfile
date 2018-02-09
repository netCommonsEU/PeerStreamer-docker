FROM debian:stable-slim
MAINTAINER Luca Baldesi <luca.baldesi@unitn.it>

# Install supervisord and automatic upgrade stuff
RUN apt-get update \
 && apt-get install -y supervisor unattended-upgrades cron \
 && rm -rf /var/lib/apt/lists/*

# Set /peerstreamer as working directory
WORKDIR /peerstreamer

# Copy required files into the container at /peerstreamer
ADD requirements.txt /peerstreamer/

RUN mkdir /peerstreamer/serf-python
ADD serf-python.tar.gz /peerstreamer/serf-python/

# Install required packages
RUN apt update && apt install -y python2.7 python-pip git libmicrohttpd-dev \
        libjansson-dev libnice-dev libssl-dev libsrtp-dev libsofia-sip-ua-dev \
        libglib2.0-dev libopus-dev libogg-dev libcurl4-openssl-dev pkg-config \
        gengetopt libtool automake

# Install python requirements
RUN pip install -r requirements.txt

# Install serf-python: the local archive have beeb checked out from github.
# Don't use the package provided with pip because it doesn't work.
RUN cd /peerstreamer/serf-python && \
        python setup.py install
RUN rm -rf /peerstreamer/serf-python

# Build peerstreamer
RUN git clone -b devel \
        https://ans.disi.unitn.it/redmine/peerstreamer-src.git \
            peerstreamer
RUN cd /peerstreamer/peerstreamer && make

# Clone psng-pyserf
RUN git clone -b source_broadcasting\
        https://ans.disi.unitn.it/redmine/psng-pyserf.git \
            psng-pyserf
RUN chmod +x psng-pyserf/psng_pyserf.py

RUN apt remove -y git automake \
        && apt autoremove -y

# Clean up APT when done.
RUN apt clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY cron-supervisord.conf /etc/supervisor/conf.d/cron.conf
COPY psng-supervisord.conf /etc/supervisor/conf.d/psng.conf
COPY pyserf-supervisord.conf /etc/supervisor/conf.d/pyserf.conf

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
