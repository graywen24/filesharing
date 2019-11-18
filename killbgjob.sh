#!/bin/bash

#to kill the process rsync.sh on standby node
for i in `ps -ef|grep rsync.sh |grep -v grep |awk '{print $2}'`; do kill -9 $i; done
