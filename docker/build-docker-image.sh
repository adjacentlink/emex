#!/bin/bash

usage="build-docker-image.sh [-r] [-p] version"

image=emex
version=
rebuild=
apply_patch=0

while getopts ":hpr" opt; do
    case $opt in
        p) apply_patch=1
           echo -e "\e[31mdo apply patches in patches_in\e[0m"
           ;;
        r) rebuild="--no-cache"
           echo "forcing rebuild (--no-cache)"
           ;;
        h) echo ${usage} && exit 0
           ;;
        \?) echo "Invalid option -$OPTARG"
            ;;
    esac
done

shift $((OPTIND-1))

if [ $# != 1 ]; then
    echo $usage
    exit 1
fi

version=$1

function tgz_patches() {
    if [ -d patches ]; then
	rm -rf patches
    fi

    mkdir -p patches

    if [ -d patches_in ]; then
	if [ $apply_patch == "1" ]; then
	    cp patches_in/* patches/
	fi
    fi

    tar -cvzf patches.tgz patches
    rm -rf patches
}


tgz_patches

docker build ${rebuild} --rm -t $image:$version -t $image:latest -f Dockerfile .

rm -f patches.tgz
