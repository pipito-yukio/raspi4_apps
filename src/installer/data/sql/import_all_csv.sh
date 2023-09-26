#!/bin/bash

# https://stackoverflow.com/questions/34736762/script-to-automat-import-of-csv-into-postgresql
#   Script to automat import of CSV into PostgreSQL

psql -Udeveloper -d sensors_pgdb -c "ALTER TABLE weather.t_weather DROP CONSTRAINT pk_weather;"
psql -Udeveloper -d sensors_pgdb -c "ALTER TABLE weather.t_weather DROP CONSTRAINT fk_device;"

# t_device.csv into t_device table
psql -Udeveloper -d sensors_pgdb -c "\copy weather.t_device FROM '/home/pi/data/sql/csv/device.csv' DELIMITER ',' CSV HEADER;"
# t_weather.csv into t_weather table
psql -Udeveloper -d sensors_pgdb -c "\copy weather.t_weather FROM '/home/pi/data/sql/csv/weather.csv' DELIMITER ',' CSV HEADER;"

# Rebuild constraint.
psql -Udeveloper -d sensors_pgdb -c "ALTER TABLE weather.t_weather ADD CONSTRAINT pk_weather PRIMARY KEY (did, measurement_time);"
psql -Udeveloper -d sensors_pgdb -c "ALTER TABLE weather.t_weather ADD CONSTRAINT fk_device FOREIGN KEY (did) REFERENCES weather.t_device (id);"
