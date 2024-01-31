#!/bin/bash

usage="usage: run-etce.sh [-d DELAYSECS] [-s RUNTOSTEP]"

delaysecsargs=

configfilearg=

while getopts ":hc:d:s:" opt; do
    case $opt in
	c) configfilearg="--config ${OPTARG}";
	   echo "config=${OPTARG}"
	   ;;
        d) delaysecsarg="--delaysecs ${OPTARG}";
           echo "delaysecs=${OPTARG}"
           ;;
        s) runtosteparg="--runtostep ${OPTARG}";
           echo "runtostep=${OPTARG}"
           ;;
        h) echo ${usage} && exit 0
           ;;
        \?) echo "Invalid option -$OPTARG"
            ;;
    esac
done

/usr/sbin/sshd -o "PermitRootLogin=yes" -o "PasswordAuthentication=no" -o "HostKeyAlgorithms=ssh-rsa"

etce-lxc start --writehosts /tmp/etce/config/doc/lxcplan.xml 

# wait for lxcs
sleep 10

etce-test run --yes ${configfilearg} ${delaysecsarg} --kill before emex /tmp/etce/config/doc/hostfile /tmp/etce/config
