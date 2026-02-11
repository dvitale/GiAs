#!/bin/bash
 FILE=$(basename $PWD)
 pgrep -x $FILE >/dev/null
 if [ $? -eq 0 ]
 then
 echo "* $FILE  is running"
 else
 echo "* $FILE  not running"
 fi

