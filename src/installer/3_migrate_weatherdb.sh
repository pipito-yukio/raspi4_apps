#!/bin/bash

# This script execute before 1_inst_udpmon.sh execute and logout terminal.
#  before export my_passwd=xxxxx

# [usage] ./migrade_weather from-date 
#    from-date required (exmaple) 2022-01-01  

# Migrate SQLite3 weather.db (export csv) into PostgeSQL 
# scp from raspi-zero:SQLite3 weather.db 
scp pi@raspi-zero:~/db/weather.db ~/data/sql/sqlite3db
exit1=$?
echo "scp paspi-zero:weather.db into sqlite3db directory >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

cd ~/data/sql

export PATH_WEATHER_DB=~/data/sql/sqlite3db/weather.db
./getcsv_from_device.sh --output-path csv
./getcsv_from_weather.sh --device-name esp8266_1 --from-date $1 --output-path csv
exit1=$?
echo "export SQLite3 db to weather.csv >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

cd ~/docker/postgres

docker-compose up -d
exit1=$?
echo "docker-compose up -d >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

# wait starting pg_ctl in container.
sleep 2

docker exec -it postgres-12 sh -c "$HOME/data/sql/import_all_csv.sh"
exit1=$?
echo "docker exec import_all_csv.sh >> status=$exit1"

docker-compose down

cd ~

echo "SQLite3 weatherdb migration to PostgreSQL complete!"

