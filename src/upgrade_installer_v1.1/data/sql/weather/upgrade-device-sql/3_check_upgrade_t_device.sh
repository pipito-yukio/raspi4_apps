#!/bin/bash

# テーブルのアップグレードと追加したデバイス一覧
echo "SELECT * FROM weather.t_device ORDER BY id;" | psql -Udeveloper -d sensors_pgdb

