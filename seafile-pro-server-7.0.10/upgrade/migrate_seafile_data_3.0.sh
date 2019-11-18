#!/bin/bash

SCRIPT=$(readlink -f "$0") # haiwen/seafile-server-1.3.0/upgrade/upgrade_xx_xx.sh
UPGRADE_DIR=$(dirname "$SCRIPT") # haiwen/seafile-server-1.3.0/upgrade/
INSTALLPATH=$(dirname "$UPGRADE_DIR") # haiwen/seafile-server-1.3.0/
TOPDIR=$(dirname "${INSTALLPATH}") # haiwen/
default_ccnet_conf_dir=${TOPDIR}/ccnet
default_seafile_data_dir=${TOPDIR}/seafile-data
default_seahub_db=${TOPDIR}/seahub.db
default_conf_dir=${TOPDIR}/conf

manage_py=${INSTALLPATH}/seahub/manage.py

export CCNET_CONF_DIR=${default_ccnet_conf_dir}
export PYTHONPATH=${INSTALLPATH}/seafile/lib/python2.6/site-packages:${INSTALLPATH}/seafile/lib64/python2.6/site-packages:${INSTALLPATH}/seafile/lib/python2.7/site-packages:${INSTALLPATH}/seahub/thirdpart:$PYTHONPATH
export PYTHONPATH=${INSTALLPATH}/seafile/lib/python2.7/site-packages:${INSTALLPATH}/seafile/lib64/python2.7/site-packages:$PYTHONPATH
export SEAFILE_LD_LIBRARY_PATH=${INSTALLPATH}/seafile/lib/:${INSTALLPATH}/seafile/lib64:${LD_LIBRARY_PATH}

echo
echo "-------------------------------------------------------------"
echo "This script would migrate  your seafile data to 3.0 layout"
echo "Press [ENTER] to contiune"
echo "-------------------------------------------------------------"
echo
read dummy

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

    export SEAFILE_CONF_DIR=$seafile_data_dir
}

function ensure_server_not_running() {
    # test whether seafile server has been stopped.
    if pgrep seaf-server 2>/dev/null 1>&2 ; then
        echo
        echo "seafile server is still running !"
        echo "stop it using scripts before upgrade."
        echo
        exit 1
    elif pgrep -f "${manage_py} run_gunicorn" 2>/dev/null 1>&2 ; then
        echo
        echo "seahub server is still running !"
        echo "stop it before upgrade."
        echo
        exit 1
    elif pgrep -f "${manage_py} run_fcgi" 2>/dev/null 1>&2 ; then
        echo
        echo "seahub server is still running !"
        echo "stop it before upgrade."
        echo
        exit 1
    fi
}

function migrate_seafile_data_format() {
    seaf_migrate=${INSTALLPATH}/seafile/bin/seaf-migrate
    echo
    echo "Now migrating your seafile data to 3.0 format. It may take a while."
    echo
    if ! LD_LIBRARY_PATH=${SEAFILE_LD_LIBRARY_PATH} ${seaf_migrate} \
            -c "${default_ccnet_conf_dir}" -d "${seafile_data_dir}" -t 100; then
        echo
        echo "Failed to migrate seafile data to 3.0 format"
        echo
        exit 1;
    fi
}

#################
# The main execution flow of the script
################

check_python_executable;
read_seafile_data_dir;
ensure_server_not_running;

export SEAFILE_CONF_DIR=$seafile_data_dir

migrate_seafile_data_format;

echo
echo "-----------------------------------------------------------------"
echo "Your seafile data have been migrated data to 3.0 layout"
echo "-----------------------------------------------------------------"
echo
