#!/bin/bash

# Create PostgreSQL container with sensors_pgdb database and weather data tables.
cd ~/docker/postgres
docker-compose up --build -d
exit1=$?
echo "Docker create PostgreSQL container >> status=$exit1"
docker-compose down
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

cd ~/
echo "Done."

