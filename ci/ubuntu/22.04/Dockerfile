FROM ubuntu:22.04

RUN mkdir -p /opt/built

# prevent failures due to interactive apt transactions
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get -y update
RUN apt-get -y upgrade --no-install-recommends

# Copy and install packages from the latest upsteam dependencies
WORKDIR /opt
RUN mkdir -p dependencies
COPY --from=gcr.io/automated-builds-303920/ubuntu22.04.waveform-resource /opt/built/* dependencies/
RUN dpkg -i dependencies/*; apt-get -y -f install

# Build tools
RUN apt-get -y install git autoconf automake libtool dh-python debhelper pkg-config python3-setuptools

RUN git clone https://github.com/adjacentlink/emex -b develop

WORKDIR emex
RUN ./autogen.sh && ./configure && make deb
RUN cp $(find .debbuild -name "*\.deb") /opt/built
RUN dpkg -i /opt/built/*; apt-get -y install -f

RUN echo 'complete'

