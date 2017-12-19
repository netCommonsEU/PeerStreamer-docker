# PeerStreamer-NG docker imange

For generating the peerstreamer docker image run the following command:

```
docker build -t peerstreamer .
```

If you intend to push the image on docker hub it is better to use directly the
tag that includes your used name. Supposing the username is xxx and the
repository is called peerstreamer:

```
docker build -t xxx/peerstreamer .
```

In order to push the new image the following command are required (and an
account on [hub.dovker](https://hub.docker.com)):

docker login (this requires username and password)
docker push xxx/peerstreamer (this implies latest as tag, use
peerstreamer:<tag> to change the version)

Run the container with the following command:

```
docker run -d peerstreamer
```

# Base image

Currently the peerstreamer docker image is based on baseimage-docker that, among
other things, provides mechanisms for easily running multiple processes (for
more information look at [here](https://github.com/phusion/baseimage-docker)).

Basic documentation for adding additional services is provided [here](https://github.com/phusion/baseimage-docker#adding-additional-daemons)

baseimage-docker provides an easy way for setting up an ssh server for logging
into the container as described [here](https://github.com/phusion/baseimage-docker#login-to-the-container-or-running-a-command-inside-it-via-ssh)


# Inspecting peerstreamer image

For debugging reasons it can be useful to have the ability to look around in the
peerstreamer image. This can be achieved with the following command:

```
docker run --rm -t -i peerstreamer /sbin/my\_init -- bash -l
```

