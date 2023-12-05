#!/bin/bash -

image=emex
version=$(grep AC_INIT ../configure.ac | awk -F, '{print $2}')
rebuild=
apply_patch=0

function usage() {
    echo "build-docker-image.sh [-r] [-p] [-v VERSION]"
    echo
    echo "options:"
    echo "   -r Rebuild all layers, equivelent to --no-cache docker build option."
    echo "   -p Developer option to apply patches in patches_in subdirectory."
    echo "   -v Set the image version number. default: $version"
    echo
}

while getopts ":hprv:" opt; do
    case $opt in
        p) apply_patch=1
           echo -e "\e[31mdo apply patches in patches_in\e[0m"
           ;;
        r) rebuild="--no-cache"
           echo "forcing rebuild (--no-cache)"
           ;;
	v) version=${OPTARG};
           echo "setting version to ${version}"
           ;;	   
        h) usage && exit 0
           ;;
        \?) echo "Invalid option -$OPTARG"
            ;;
    esac
done

shift $((OPTIND-1))

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


echo "Building docker image emex:$version"

tgz_patches

docker build ${rebuild} --rm -t $image:$version -t $image:latest -f Dockerfile .

rm -f patches.tgz
