#!/bin/bash

# postgres-12 container on sensors_pgdb
cd /home/pi/data/sql/weather/upgrade-device-sql
# デバイス追加SQL実行
psql -Udeveloper -d sensors_pgdb < 05_add_record_t_device.sql
exit1=$?
echo "05_add_record_t_device.sql >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

