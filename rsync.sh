#!/bin/bash
#rsync auto sync script with inotify
current_date=$(date +%Y%m%d_%H%M%S)
source_path=/storage
log_file=/var/log/rsync_client.log

#rsync
standby_server=10.0.0.146  #app04
rsync_user=root
rsync_pwd=/etc/rsync.password
rsync_module=module_test
INOTIFY_EXCLUDE='(.*/*\.log|.*/*\.swp)$|^/tmp/src/mail/(2014|20.*/.*che.*)'
RSYNC_EXCLUDE='/etc/rsyncd.d/rsync_exclude.lst'

#rsync client pwd check

#inotify_function
inotify_fun(){
    /usr/bin/inotifywait -mrq --timefmt '%Y/%m/%d-%H:%M:%S' --format '%T %w %f' \
           -e modify,delete,create,move,attrib ${source_path} \
          | while read file
      do
          /usr/bin/rsync -hPtpraz --bwlimit=20000 --delete-delay /storage/  $standby_server:/storage >> $log_file
      done
}

#inotify log
inotify_fun
#inotify_fun >> ${log_file} 2>&1 &
