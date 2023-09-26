#!/bin/bash

# アップグレードしたデバイステーブルの確認
docker exec -it postgres-12 sh -c "$HOME/data/sql/weather/upgrade-device-sql/3_check_upgrade_t_device.sh"

