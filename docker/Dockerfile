# start with a base pre-built base
FROM rockylinux:8

ARG defaultbranch=develop

ARG emanebranch=$defaultbranch
ARG opentestpointbranch=$defaultbranch
ARG openstatisticbranch=$defaultbranch
ARG opentestpointlabtoolsbranch=$defaultbranch
ARG opentestpointemanebranch=$defaultbranch
ARG opentestpointsystembranch=$defaultbranch
ARG opentestpointiptrafficbranch=$defaultbranch
ARG opentestpointiproutebranch=$defaultbranch
ARG opentestpointmgenbranch=$defaultbranch
ARG pythonetcebranch=$defaultbranch
ARG emanespectrumtoolsbranch=$defaultbranch
ARG emanemodelltebranch=$defaultbranch
ARG srsRANemanebranch=$defaultbranch
ARG opentestpointltebranch=$defaultbranch
ARG emanenodedirectorbranch=$defaultbranch
ARG waveformresourcebranch=$defaultbranch
ARG emanejammersimplebranch=$defaultbranch
ARG emexbranch=$defaultbranch
ARG opentestpointprobeemexbranch=$defaultbranch

# update all installed built-packages
RUN dnf -y update && \
    dnf -y install git epel-release dnf-plugins-core patch && \
    dnf config-manager --set-enabled powertools

RUN dnf clean all

WORKDIR /opt
COPY patches.tgz .
RUN tar -xvzf patches.tgz

RUN git clone https://github.com/adjacentlink/emane.git -b $emanebranch && \
    git clone https://github.com/adjacentlink/opentestpoint.git -b $opentestpointbranch && \
    git clone https://github.com/adjacentlink/openstatistic.git -b $openstatisticbranch && \
    git clone https://github.com/adjacentlink/opentestpoint-probe-emane.git -b $opentestpointemanebranch && \
    git clone https://github.com/adjacentlink/opentestpoint-probe-system.git -b $opentestpointsystembranch && \
    git clone https://github.com/adjacentlink/opentestpoint-probe-iptraffic.git -b $opentestpointiptrafficbranch && \
    git clone https://github.com/adjacentlink/opentestpoint-probe-iproute.git -b $opentestpointiproutebranch && \
    git clone https://github.com/adjacentlink/opentestpoint-labtools.git -b $opentestpointlabtoolsbranch && \
    git clone https://github.com/adjacentlink/opentestpoint-probe-mgen.git -b $opentestpointmgenbranch && \
    git clone https://github.com/adjacentlink/python-etce.git -b $pythonetcebranch && \
    git clone https://github.com/adjacentlink/emane-spectrum-tools.git -b $emanespectrumtoolsbranch && \
    git clone https://github.com/adjacentlink/emane-model-lte -b $emanemodelltebranch && \
    git clone https://github.com/adjacentlink/srsRAN-emane -b $srsRANemanebranch && \
    git clone https://github.com/adjacentlink/opentestpoint-probe-lte -b $opentestpointltebranch && \
    git clone https://github.com/adjacentlink/emane-node-director -b $emanenodedirectorbranch && \
    git clone https://github.com/adjacentlink/waveform-resource -b $waveformresourcebranch && \
    git clone https://github.com/adjacentlink/emane-jammer-simple -b $emanejammersimplebranch && \
    git clone https://github.com/adjacentlink/emex -b $emexbranch && \
    git clone https://github.com/adjacentlink/opentestpoint-probe-emex -b $opentestpointprobeemexbranch

## EMANE
WORKDIR /opt/emane
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    dnf -y install gcc-c++ make autoconf automake libtool rpm-build python3-setuptools \
                   libxml2-devel libpcap-devel pcre-devel libuuid-devel python3-devel \
                   python3-protobuf protobuf-devel && \
    touch ../patches/emane.patch && \
    patch -p1 < ../patches/emane.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "emane*\x86_64.rpm") $(find .rpmbuild -name "emane*\noarch.rpm") $(find .rpmbuild -name "python*\.rpm")

## OpenTestPoint
WORKDIR /opt/opentestpoint
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    dnf -y install sqlite-devel zeromq-devel && \
    touch ../patches/opentestpoint.patch && \
    patch -p1 < ../patches/opentestpoint.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## OpenStatistic
WORKDIR /opt/openstatistic
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/openstatistic.patch && \
    patch -p1 < ../patches/openstatistic.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## EMANE Probe
WORKDIR /opt/opentestpoint-probe-emane
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-probe-emane.patch && \
    patch -p1 < ../patches/opentestpoint-probe-emane.patch && \
    ./autogen.sh && ./configure && make rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## System Probe
WORKDIR /opt/opentestpoint-probe-system
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-probe-system.patch && \
    patch -p1 < ../patches/opentestpoint-probe-system.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## iptraffic Probe
WORKDIR /opt/opentestpoint-probe-iptraffic
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-probe-iptraffic.patch && \
    patch -p1 < ../patches/opentestpoint-probe-iptraffic.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## iproute Probe
WORKDIR /opt/opentestpoint-probe-iproute
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-probe-iproute.patch && \
    patch -p1 < ../patches/opentestpoint-probe-iproute.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## ETCE
WORKDIR /opt/python-etce
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/python-etce.patch && \
    patch -p1 < ../patches/python-etce.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## EMANE Spectrum tools
WORKDIR /opt/emane-spectrum-tools
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/emane-spectrum-tools.patch && \
    patch -p1 < ../patches/emane-spectrum-tools.patch && \
    export emane_SRC_ROOT=/opt/emane && ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## LTE Model
WORKDIR /opt/emane-model-lte
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/emane-model-lte.patch && \
    patch -p1 < ../patches/emane-model-lte.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## srsRAN-emane
WORKDIR /opt/srsRAN-emane
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    dnf -y install cmake fftw3-devel mbedtls-devel lksctp-tools-devel libconfig-devel boost-devel redhat-lsb-core && \
    touch ../patches/srsRAN-emane.patch && \
    patch -p1 < ../patches/srsRAN-emane.patch && \
    mkdir build && \
    cd build && \
    cmake .. && make && make -j $(nproc) package && \
    dnf -y install *\.rpm

## LTE Probe
WORKDIR /opt/opentestpoint-probe-lte
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-probe-lte.patch && \
    patch -p1 < ../patches/opentestpoint-probe-lte.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## Node Director
WORKDIR /opt/emane-node-director
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/emane-node-director.patch && \
    patch -p1 < ../patches/emane-node-director.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## MGEN Probe
WORKDIR /opt/opentestpoint-probe-mgen
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-probe-mgen.patch && \
    patch -p1 < ../patches/opentestpoint-probe-mgen.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## Waveform Resource
WORKDIR /opt/waveform-resource
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/waveform-resource.patch && \
    patch -p1 < ../patches/waveform-resource.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## OpenTestpoint Labtools
WORKDIR /opt/opentestpoint-labtools
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-labtools.patch && \
    patch -p1 < ../patches/opentestpoint-labtools.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## EMANE Jammer Simple
WORKDIR /opt/emane-jammer-simple
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/emane-jammer-simple.patch && \
    patch -p1 < ../patches/emane-jammer-simple.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## EMEX
WORKDIR /opt/emex
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/emex.patch && \
    patch -p1 < ../patches/emex.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## OpentTestpoint Probe EMEX
WORKDIR /opt/opentestpoint-probe-emex
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit && \
    touch ../patches/opentestpoint-probe-emex.patch && \
    patch -p1 < ../patches/opentestpoint-probe-emex.patch && \
    ./autogen.sh && ./configure && make -j $(nproc) rpm && \
    dnf -y install $(find .rpmbuild -name "*\.x86_64.rpm") $(find .rpmbuild -name "*\.noarch.rpm")

## Collect
WORKDIR /opt
RUN mkdir -p rpms && \
    cp -n $(find . -name "*\x86_64.rpm") rpms && \
    cp -n $(find . -name "*\noarch.rpm") rpms && \
    cp -n $(find . -name "*\.commit") rpms && \
    chmod -R 777 rpms

## Build and Install mgen
WORKDIR /opt
RUN dnf install -y libnetfilter_queue-devel libxml2-devel libpcap-devel
RUN  git clone https://github.com/USNavalResearchLaboratory/mgen
WORKDIR mgen
RUN git rev-parse $(git branch --show-current) > $(basename $(pwd)).commit
RUN git submodule update --init
RUN cd protolib/makefiles && make -f Makefile.linux && cd ../../makefiles && make -f Makefile.linux && cp mgen /usr/local/bin

## Build lxc 4.0.10 RPMs from SRCRPM
WORKDIR /opt
COPY dependencies/lxc-4.0.10-1.fc35.src.rpm .
RUN rpm -ivh lxc-4.0.10-1.fc35.src.rpm
WORKDIR /root/rpmbuild/SPECS
RUN dnf install -y docbook2X doxygen openssl-devel pam-devel libseccomp-devel bash-completion libcap-devel
RUN rpmbuild -ba lxc.spec && dnf install -y /root/rpmbuild/RPMS/noarch/*\.rpm /root/rpmbuild/RPMS/x86_64/*\.rpm

COPY dependencies/emane-node-view-bundle.tar.bz2 .
RUN dnf install -y bzip2 python3-virtualenv && \
    tar -xvjf emane-node-view-bundle.tar.bz2 && \
    cd emane-node-view-bundle && \
    ./build-virtualenv.sh -d /opt -p dist -r requirements.txt emane-node-view

## install other needed tools. procps-ng for ps
RUN dnf install -y socat iptables procps-ng && \
    dnf install -y openssh-clients && \
    dnf clean all

RUN update-alternatives --set python /usr/bin/python3

## Create SSH keys
WORKDIR /root
RUN mkdir .ssh
WORKDIR .ssh
RUN  ssh-keygen -b 4096 -P "" -m PEM -t rsa -f id_rsa && cp id_rsa.pub authorized_keys && touch known_hosts

## Generate sshd system keys
RUN ssh-keygen -A

# Clean
WORKDIR /opt
RUN rm -rf emane && \
    rm -rf emane-jammer-simple && \
    rm -rf emane-model-lte && \
    rm -rf emane-node-director && \
    rm -rf emane-spectrum-tools && \
    rm -rf emex && \
    rm -f lxc-4.0.10-1.fc35.src.rpm && \
    rm -rf mgen && \
    rm -rf openstatistic && \
    rm -rf opentestpoint && \
    rm -rf opentestpoint-labtools && \
    rm -rf opentestpoint-probe-emane && \
    rm -rf opentestpoint-probe-emex && \
    rm -rf opentestpoint-probe-iproute && \
    rm -rf opentestpoint-probe-iptraffic && \
    rm -rf opentestpoint-probe-lte && \
    rm -rf opentestpoint-probe-mgen && \
    rm -rf opentestpoint-probe-system && \
    rm -rf patches && \
    rm -f patches.tgz && \
    rm -rf python-etce && \
    rm -rf srsRAN-emane && \
    rm -rf waveform-resource

# import scripts
WORKDIR /opt
COPY dependencies/run-emexcontainerd.sh /opt
RUN chmod 755 /opt/run-emexcontainerd.sh

COPY dependencies/run-etce.sh /opt
RUN chmod 755 /opt/run-etce.sh

CMD ["/opt/run-emexcontainerd.sh"]

