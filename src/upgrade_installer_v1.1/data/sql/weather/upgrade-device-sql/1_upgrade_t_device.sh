#!/bin/bash

# postgres-12 container on sensors_pgdb
cd /home/pi/data/sql/weather/upgrade-device-sql
# デバイス名に説明列を追加 ※既存テーブルのレコードがあるため NOT NULL制約なしの列追加
psql -Udeveloper -d sensors_pgdb < 02_alter_t_device.sql
exit1=$?
echo "02_alter_t_device.sql >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

sleep 1

# 既存デバイステーブルに追加した列を更新
psql -Udeveloper -d sensors_pgdb < 03_update_existing_device.sql
exit1=$?
echo "03_update_existing_device.sql >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

sleep 1

# デバイス名の説明列に NOT NULL制約を追加
psql -Udeveloper -d sensors_pgdb < 04_alter_t_device_set_notnull.sql
exit1=$?
echo "04_alter_t_device_set_notnull.sql >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

