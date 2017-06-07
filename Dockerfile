# For now let's start from Ubuntu 16.04 LTS
FROM ubuntu:16.04

# Set /peerstreamer as working directory
WORKDIR /peerstreamer

# Copy required files into the container at /peerstreamer
ADD requirements.txt start.sh psng-pyserf.py /peerstreamer/

# Install required packages
RUN apt update && apt install -y python2.7 python-pip

# Install python requirements
RUN pip install -r requirements.txt

# Start services
# CMD["python", "psng-pyserf.py", "-t", "psngc", "-a", "127.0.0.1", "-p", \
#         "7373", "bg", "/tmp/channels.db"]
CMD ["bash", "start.sh"]
