#!/bin/bash

SCRIPT=$(readlink -f "$0")
INSTALLPATH=$(dirname "${SCRIPT}")
TOPDIR=$(dirname "${INSTALLPATH}")
default_ccnet_conf_dir=${TOPDIR}/ccnet
central_config_dir=${TOPDIR}/conf
pro_pylibs_dir=${INSTALLPATH}/pro/python
pidfile=${INSTALLPATH}/runtime/index_master.pid


script_name=$0
function usage () {
    echo "Usage: "
    echo
    echo "  $(basename ${script_name}) { start | stop | restart | python-env }"
}

if [[ $1 != "start" && $1 != "stop" && $1 != "restart" && $1 != "python-env" ]]; then
    usage;
    exit 1;
fi

function check_python_executable() {
    if [[ "$PYTHON" != "" && -x $PYTHON ]]; then
        return 0
    fi

    if which python2.7 2>/dev/null 1>&2; then
        PYTHON=python2.7
    elif which python27 2>/dev/null 1>&2; then
        PYTHON=python27
    else
        echo
        echo "Can't find a python executable of version 2.7 or above in PATH"
        echo "Install python 2.7+ before continue."
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
}

function prepare_log_dir() {
    logdir=${TOPDIR}/logs
    if ! [[ -d ${logsdir} ]]; then
        if ! mkdir -p "${logdir}"; then
            echo "ERROR: failed to create logs dir \"${logdir}\""
            exit 1
        fi
    fi
    export LOG_DIR=${logdir}
}

function before_start() {
    check_python_executable;
    prepare_log_dir;
    read_seafile_data_dir;

    export SEAFILE_CONF_DIR=${seafile_data_dir}
    export SEAFILE_CENTRAL_CONF_DIR=${central_config_dir}
    export SEAFES_DIR=$pro_pylibs_dir/seafes
    export PYTHONPATH=${INSTALLPATH}/seafile/lib/python2.6/site-packages:${INSTALLPATH}/seafile/lib64/python2.6/site-packages:${INSTALLPATH}/seahub:${INSTALLPATH}/seahub/thirdpart:$PYTHONPATH
    export PYTHONPATH=${INSTALLPATH}/seafile/lib/python2.7/site-packages:${INSTALLPATH}/seafile/lib64/python2.7/site-packages:$PYTHONPATH
    export PYTHONPATH=$PYTHONPATH:$pro_pylibs_dir
    export PYTHONPATH=$PYTHONPATH:${INSTALLPATH}/seahub-extra/
    export PYTHONPATH=$PYTHONPATH:${INSTALLPATH}/seahub-extra/thirdparts
    export EVENTS_CONFIG_FILE=${SEAFILE_CENTRAL_CONF_DIR}/seafevents.conf
    export INDEX_MASTER_CONFIG_FILE=${SEAFILE_CENTRAL_CONF_DIR}/index-master.conf
}

run_python() {
    before_start;
    $PYTHON ${@:2}
}

start_index_master() {
    before_start;
    nohup $PYTHON -m seafes.index_master --loglevel debug --logfile ${logdir}/index_master.log start & echo $! > $pidfile
    sleep 2
    if ! pgrep -f "seafes.index_master" 2>/dev/null 1>&2; then
        printf "\033[33mError:Index master failed to start.\033[m\n"
        echo "Please try to run \"./run_index_master.sh start\" again"
        exit 1;
    fi
    echo
    echo "Index master is started"
    echo
}

stop_index_master() {
    if pgrep -f "seafes.index_worker" 2>/dev/null 1>&2; then
        printf "\033[33mError:Index worker need be stopped first.\033[m\n"
        exit 1;
    fi

    if [[ -f ${pidfile} ]]; then
        pid=$(cat "${pidfile}")
        echo "Stopping index master ..."
        kill ${pid}
        rm -f ${pidfile}
        return 0
    else
        echo "Index master is not running"
    fi
}

case $1 in 
    "start" )
        start_index_master;
        ;;
    "stop" )
        stop_index_master;
        ;;
    "restart" )
        stop_index_master
        sleep 2
        start_index_master
        ;;
    "python-env" )
        run_python "$@"
        ;;
esac

