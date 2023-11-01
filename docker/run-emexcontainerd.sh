#!/bin/bash

usage="usage: run-emexcontainerd.sh"

loglevel=info

logfile=/tmp/etce/emexcontainerd.log

while getopts ":hl:" opt; do
    case $opt in
	l) loglevel="${OPTARG}";
	   echo "loglevel=${loglevel}"
	   ;;
        h) echo ${usage} && exit 0
           ;;
        \?) echo "Invalid option -$OPTARG"
            ;;
    esac
done

/usr/sbin/sshd -o "PermitRootLogin=yes" -o "PasswordAuthentication=no" -o "HostKeyAlgorithms=ssh-rsa"
ulimit -c unlimited
emexcontainerd -l ${loglevel} -f ${logfile}
