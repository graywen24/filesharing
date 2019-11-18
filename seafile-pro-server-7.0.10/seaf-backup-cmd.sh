#!/bin/bash

# This is a wrapper shell script for the real seaf-backup command.
# It prepares necessary environment variables and exec the real script.

# requires python 2.6 or 2.7
function check_python_executable() {
    if [[ "$PYTHON" != "" && -x $PYTHON ]]; then
        return 0
    fi
        
    if which python2.7 2>/dev/null 1>&2; then
        PYTHON=python2.7
    elif which python27 2>/dev/null 1>&2; then
        PYTHON=python27
    elif which python2.6 2>/dev/null 1>&2; then
        PYTHON=python2.6
    elif which python26 2>/dev/null 1>&2; then
        PYTHON=python26
    else
        echo 
        echo "Can't find a python executable of version 2.6 or above in PATH"
        echo "Install python 2.6+ before continue."
        echo "Or if you installed it in a non-standard PATH, set the PYTHON enviroment varirable to it"
        echo 
        exit 1
    fi
}

check_python_executable

# seafile cli client requires the argparse module
if ! $PYTHON -c 'import argparse' 2>/dev/null 1>&2; then
    echo
    echo "Python argparse module is required"
    echo "see [https://pypi.python.org/pypi/argparse]"
    echo
    exit 1
fi

SCRIPT=$(readlink -f "$0")
INSTALLPATH=$(dirname "${SCRIPT}")
TOPDIR=$(dirname "${INSTALLPATH}")
central_config_dir=${TOPDIR}/conf
default_ccnet_conf_dir=${TOPDIR}/ccnet

function validate_ccnet_conf_dir () {
    if [[ ! -d ${default_ccnet_conf_dir} ]]; then
        echo "Error: there is no ccnet config directory."
        echo "Have you run setup-seafile.sh before this?"
        echo ""
        exit -1;
    fi
}

function read_seafile_data_dir () {
    seafile_ini=${default_ccnet_conf_dir}/seafile.ini
    if [[ ! -f ${seafile_ini} ]]; then
        echo "${seafile_ini} not found. Now quit"
        exit 1
    fi
    seafile_data_dir=$(cat "${seafile_ini}")
    if [[ ! -d ${seafile_data_dir} ]]; then
        echo "Your seafile server data directory \"${seafile_data_dir}\" is invalid or doesn't exits."
        echo "Please check it first, or create this directory yourself."
        echo ""
        exit 1;
    fi
}

validate_ccnet_conf_dir
read_seafile_data_dir

SEAFILE_PYTHON_PATH=${INSTALLPATH}/seafile/lib/python2.6/site-packages:${INSTALLPATH}/seafile/lib64/python2.6/site-packages:${INSTALLPATH}/seafile/lib/python2.7/site-packages:${INSTALLPATH}/seafile/lib64/python2.7/site-packages

SEAF_BACKUP_CMD=${INSTALLPATH}/seaf-backup-cmd.py

export PYTHONPATH=${SEAFILE_PYTHON_PATH}:${PYTHONPATH}
export CCNET_CONF_DIR=${default_ccnet_conf_dir}
export SEAFILE_CONF_DIR=${seafile_data_dir}
export SEAFILE_CENTRAL_CONF_DIR=${central_config_dir}
$PYTHON ${SEAF_BACKUP_CMD} "$@"
