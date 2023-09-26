#!/bin/bash

# sensors_pgdbのデバイステーブルに説明列を追加し既存のレコードを更新する
docker exec -it postgres-12 sh -c "$HOME/data/sql/weather/upgrade-device-sql/1_upgrade_t_device.sh"
exit1=$?
echo "1_upgrade_t_device.sh >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

# 複数のデバイスを登録する
docker exec -it postgres-12 sh -c "$HOME/data/sql/weather/upgrade-device-sql/2_add_devices_to_t_device.sh"
exit1=$?
echo "2_add_devices_to_t_device.sh >> status=$exit1"
if [ $exit1 -ne 0 ]; then
   exit $exit1
fi

# ※通常ならマイグレーション用の古いスクリプトとCSVディレクトリ削除
#cd ~/data/sql
#rm -rf csv sqlite3db
#rm -f *.sh

echo "Done."

