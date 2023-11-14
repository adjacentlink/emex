#!/bin/bash

usage="extract-rpms.sh version"

tag=emex
version=
uid=$UID

if [ $# != 1 ]; then
    echo $usage
    exit 1
fi

version=$1

dockerimage="$tag:$version"

outdir=emex-$version-rpms

if [ -e $outdir ];
then
    if [ -d $outdir ];
    then
	echo "Deleting $outdir"
	sudo rm -rf $outdir
    fi
fi
mkdir -p $outdir

echo "Copy built-packages from $image to ./$outdir"
docker run -u root --entrypoint=/bin/sh --rm -i -v $(pwd)/$outdir:/mnt $dockerimage <<COMMANDS
cp -R /opt/rpms/* /mnt
chown $uid.$uid /mnt/*
COMMANDS
