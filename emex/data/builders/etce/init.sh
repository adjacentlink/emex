#!/bin/bash -
# make node for tun device
mkdir /dev/net
mknod /dev/net/tun c 10 200
pidfile="${lxc_directory}/var/run/sshd.pid"
/usr/sbin/sshd -o "PidFile=$pidfile" -o "PermitRootLogin=yes" -o "PasswordAuthentication=no" -o "HostKeyAlgorithms=ssh-rsa"
