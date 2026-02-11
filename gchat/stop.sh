#!/bin/bash

cd "$(dirname "$0")"
 FILE=$(basename $PWD)
 TIMESTAMP=$(date --iso-8601=seconds)
 pkill $FILE
 if [ $? -eq 0 ]
 then
 echo "* $FILE  end : $TIMESTAMP" >>./log/stop.log
 echo "* $FILE  stopped"
 else
 echo "* $FILE  not stopped. Is it really running?"
 fi

