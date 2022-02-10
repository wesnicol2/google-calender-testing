#!/bin/bash

# This script will pull the latest changes from the branch indicated
# PARAMETERS: 
#	(Required) <local_path_to_repo>
#	(Required) <branch_name>

REPO_PATH=${1}
BRANCH_NAME=${2}
if [ "$#" -ne 2 ] ; then
	printf "Incorrect number of arguments. Exiting.\n"
	exit 1
fi

if [ ! -d ${REPO_PATH} ] ; then
	printf "Invalid repo path [${REPO_PATH}] given. Exiting.\n"
	exit 1
fi

cd ${REPO_PATH}
git fetch

if [[ -n $(git branch --list ${BRANCH_NAME}) ]] ; then
	echo "$BRANCH_NAME found!"
	git checkout ${BRANCH_NAME}
	git pull origin ${BRANCH_NAME}
else
	REPO_NAME=`basename ${REPO_PATH}`
	printf "Branch [${BRANCH_NAME}] not found in ${REPO_NAME}. Exiting.\n"
	exit 1	
fi
