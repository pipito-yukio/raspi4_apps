import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict

from psycopg2.extensions import connection, cursor
from psycopg2 import DatabaseError

"""
t_deviceテーブルデータ取得クラス
"""


@dataclass(frozen=True)
class DeviceRecord:
    """ t_device テーブルレコードクラス """
    id: int
    name: str
    description: str


@dataclass(frozen=True)
class _DeviceItem:
    """ DeviceRecord から id を除いたクラス ※中間利用"""
    name: str
    description: str


class DeviceDao(object):
    # 全センサーディバイス取得
    _QUERY_DEVICES = "SELECT id,name,description FROM weather.t_device ORDER BY id;"
    # 指定したデバイス名の存在チェック
    _QUERY_EXISTS_DEVICE = "SELECT count(id) FROM weather.t_device WHERE name=%(name)s;"

    def __init__(self, conn: connection, logger: logging.Logger = None):
        self.logger = logger
        self.conn = conn

    def get_devices(self) -> List[DeviceRecord]:
        """
        t_deviceテーブルの全てのレコードを取得する
        :return: List[DeviceRecord]
        :raise: DatabaseError
        """
        devices: List[DeviceRecord] = []
        try:
            cur: cursor
            with self.conn.cursor() as cur:
                cur.execute(self._QUERY_DEVICES)
                rows: List[Tuple[int, str, str]] = cur.fetchall()
                if self.logger is not None:
                    self.logger.debug(f"rows.size: {len(rows)}")
                for row in rows:
                    data: DeviceRecord = DeviceRecord(row[0], row[1], row[2])
                    devices.append(data)
        except DatabaseError as exp:
            if self.logger is not None:
                self.logger.warning(exp)
            raise exp
        return devices

    def exists(self, device_name: str) ->bool:
        """
        デバイス名が t_deviceテーブルに存在するかチェックする
        :return: 存在したら True
        :raise: DatabaseError
        """
        result: bool = False
        try:
            cur: cursor
            with self.conn.cursor() as cur:
                cur.execute(self._QUERY_EXISTS_DEVICE, {'name': device_name})
                row: Tuple[int] = cur.fetchone()
                if self.logger is not None:
                    self.logger.debug(f"row: {row}")
                # 存在したら0以外
                result = row[0] != 0
        except DatabaseError as exp:
            if self.logger is not None:
                self.logger.warning(exp)
            raise exp
        return result


    @classmethod
    def to_dict(cls, devices: List[DeviceRecord]) -> List[Dict]:
        """
        デバイスリストを辞書オブジェクトのリストに変換 ※JSONレスポンス用
        :param devices: List[DeviceRecord]
        :return: 辞書オブジェクトのリスト
        """
        dict_list: List[Dict] = []
        for device in devices:
            dict_list.append(asdict(device))
        return dict_list

    @classmethod
    def to_dict_without_id(cls, devices: List[DeviceRecord]) -> List[Dict]:
        """
        デバイスリストのレコードからid列を除いた辞書オブジェクトのリストに変換 ※JSONレスポンス用
        :param devices: List[DeviceRecord]
        :return: id列を除いた辞書オブジェクトのリスト
        """
        dict_list: List[Dict] = []
        for device in devices:
            device_item: _DeviceItem = _DeviceItem(device.name, device.description)
            dict_list.append(asdict(device_item))
        return dict_list
