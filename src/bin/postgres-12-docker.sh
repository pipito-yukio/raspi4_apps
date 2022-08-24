#!/bin/bash

docker_compose=$(which docker-compose)

case "$1" in
  start)
    cd $2 # Directory in docker-compose.yml
    $docker_compose up -d
    systemd-notify --ready
    echo "PostgreSQL container ready!"
    # After udp-weather-mon.service, webapp-plot-weather.service
    cd ~
    ;;
  stop)
    # At shutdown
    cd $2
    $docker_compose down
    echo "PostgreSQL container down."
    cd ~
    ;;
  *)
    exit 1
    ;; 
esac

