#!/bin/bash
psql -Upostgres -f initdb/10_createdb_sensors.sql
sleep 3
psql -Upostgres -d sensors_pgdb -f initdb/11_weather_db.sql

