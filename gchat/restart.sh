#!/bin/bash

 DIR=$(dirname $0)
 cd ${DIR}
 FILE=$(basename $PWD)
 N=$(pidof $FILE |grep -v |wc -l)
 if [ $N -eq 0 ]
 then
	 echo  ${DIR}/stop.sh
	 ${DIR}/stop.sh
	 ${DIR}/run.sh
 fi

