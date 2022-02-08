#! /bin/bash

# This script will gather all files larger than a given size from the given log directory
# then copy those files to a new given folder

LOG_DIR=${1%/}
DEST_DIR=${2%/}

if [ "$#" -ne 2 ] ; then
	printf "Incorrect number of arguments. Exiting.\n"
	exit 1
fi

if [ ! -d "${LOG_DIR}" ] ; then
	printf "Invalid log dir given: [${LOG_DIR}]\n Exiting.\n"
	exit 1
fi

mkdir -p ${DEST_DIR}
if [ ! -d "${DEST_DIR}" ] ; then
	printf "Invalid destination dir given: [${DEST_DIR}]\n Exiting.\n"
	exit 1
fi

REGEX='^.*Events\supdated:\s0.*$'
for file in ${LOG_DIR}/*.log ; do
	last_line=`tail -n 1 $file`
	if [[ ! $last_line =~ $REGEX ]] ; then
		cp ${file} ${DEST_DIR} 
	fi
done

