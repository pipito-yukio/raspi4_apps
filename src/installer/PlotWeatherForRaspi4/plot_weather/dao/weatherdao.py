import logging
from datetime import date
from io import StringIO
from typing import List, Tuple, Optional
from psycopg2._psycopg import connection
from ..db.sqlite3conv import strdate2timestamp
from ..util.dateutil import addDayToString, nextYearMonth

""" 気象データDAOクラス """

HEADER_WEATHER: str = '"did","measurement_time","temp_out","temp_in","humid","pressure"'


def _csvToStringIO(
        tupledlist: List[Tuple[int, str, float, float, float, float]],
        require_header=True) -> StringIO:
    str_buffer = StringIO()
    if require_header:
        str_buffer.write(HEADER_WEATHER+"\n")

    for (did, m_time, temp_in, temp_out, humid, pressure) in tupledlist:
        line = f'{did},"{m_time}",{temp_in},{temp_out},{humid},{pressure}\n'
        str_buffer.write(line)

    # StringIO need Set first position
    str_buffer.seek(0)
    return str_buffer


class WeatherDao:

    _QUERY_WEATHER_LASTREC: str = """
SELECT
  to_char(measurement_time,'YYYY-MM-DD HH24:MI') as measurement_time
  , temp_out, temp_in, humid, pressure
FROM
  weather.t_weather
WHERE
  did=(SELECT id FROM weather.t_device WHERE name=%(name)s)
  AND
  measurement_time = (SELECT max(measurement_time) FROM weather.t_weather);
"""

    _QUERY_GROUPBY_DAYS: str = """
SELECT
  to_char(measurement_time, 'YYYY-MM-DD') as groupby_days
FROM
  weather.t_weather
WHERE
  did=(SELECT id FROM weather.t_device WHERE name=%(name)s)
  AND
  to_char(measurement_time, 'YYYY-MM-DD') >= '%s(groupby_days)s'
GROUP BY to_char(measurement_time, 'YYYY-MM-DD')
ORDER BY to_char(measurement_time, 'YYYY-MM-DD');
    """

    _QUERY_GROUPBY_MONTHS: str = """
SELECT
  to_char(measurement_time, 'YYYY-MM') as groupby_months
FROM
  weather.t_weather
WHERE
  did=(SELECT id FROM weather.t_device WHERE name=%(name)s)
  AND
  to_char(measurement_time, 'YYYY-MM') >= %(groupby_months)s
  GROUP BY to_char(measurement_time, 'YYYY-MM')
  ORDER BY to_char(measurement_time, 'YYYY-MM') DESC;
"""

    _QUERY_TODAY_DATA: str = """
SELECT
   did, to_char(measurement_time,'YYYY-MM-DD HH24:MI') as measurement_time
   , temp_out, temp_in, humid, pressure
FROM
   weather.t_weather
WHERE
   did=(SELECT id FROM weather.t_device WHERE name=%(name)s)
   AND
   measurement_time >= to_timestamp(%(today)s, 'YYYY-MM-DD HH24:MI:SS')
ORDER BY did, measurement_time;
"""

    _QUERY_RANGE_DATA: str = """
SELECT
   did, to_char(measurement_time,'YYYY-MM-DD HH24:MI') as measurement_time
   , temp_out, temp_in, humid, pressure
FROM
   weather.t_weather
WHERE
   did=(SELECT id FROM weather.t_device WHERE name=%(name)s)
   AND (
     measurement_time >= to_timestamp(%(from_date)s, 'YYYY-MM-DD HH24::MI:SS')
     AND
     measurement_time < to_timestamp(%(to_next_date)s, 'YYYY-MM-DD HH24:MI:SS')
   )
ORDER BY did, measurement_time;
"""

    def __init__(self, conn: connection, logger: Optional[logging.Logger]=None):
        self.conn = conn
        self.logger = logger
        self.logger_debug: bool = False
        if self.logger is not None:
            self.logger_debug = (self.logger.getEffectiveLevel() <= logging.DEBUG)

    def getLastData(self,
                    device_name: str) -> Tuple[str, float, float, float, float]:
        """観測デバイスの最終レコードを取得する

        Args:
          device_name str: 観測デバイス名

        Returns:
          tuple: (measurement_time[%Y %m %d %H %M], temp_out, temp_in, humid, pressure)
        """
        with self.conn.cursor() as cursor:
            cursor.execute(self._QUERY_WEATHER_LASTREC, {'name': device_name})
            row = cursor.fetchone()
            if self.logger is not None and self.logger_debug:
                self.logger.debug("row: {}".format(row))

        return row

    def _getDateGroupByList(self,
                            qrouping_sql: str,
                            device_name: str,
                            start_date: str,
                            groupby_name='groupby_days') -> List[str]:
        """観測デバイスのグルーピングSQLに対応した日付リストを取得する

        Args:
            qrouping_sql str: グルーピングSQL
            device_name str: 観測デバイス名
            start_date str: 検索開始日付
            groupby_name: 'groupby_days' | 'groupby_months'

        Returns:
          list: 文字列の日付 (年月 | 年月日)
        """
        if self.logger is not None and self.logger_debug:
            self.logger.debug("{}, {}".format(device_name, start_date))
        # Check start_date
        strdate2timestamp(start_date)

        with self.conn.cursor() as cursor:
            cursor.execute(qrouping_sql, {'name': device_name, groupby_name: start_date})
            # fetchall() return tuple list [(?,), (?,), ..., (?,)]
            tupledlist: List[Tuple[str, ]] = cursor.fetchall()
            if self.logger is not None and self.logger_debug:
                self.logger.debug("tupledlist: {}".format(tupledlist))
            # tuple -> list
            result = [item for (item,) in tupledlist]

        return result

    def getGroupbyDays(self, device_name: str, start_date: str) -> List[str]:
        """観測デバイスの年月日にグルーピングしたリストを取得する

        Args:
            device_name str: 観測デバイス名
            start_date str: 検索開始年月日

        Returns:
            list[str]: 年月日リスト(%Y-%m-%d)
        """
        return self._getDateGroupByList(
            self._QUERY_GROUPBY_DAYS, device_name, start_date,
            groupby_name="groupby_days"
        )

    def getGroupbyMonths(self, device_name: str, start_date: str) -> List[str]:
        """観測デバイスの年月にグルーピングしたリストを取得する

        Args:
            device_name str: 観測デバイス名
            start_date str: 検索開始年月日

        Returns:
            list[str]: 降順の年月リスト(%Y-%m)
        """
        return self._getDateGroupByList(
            self._QUERY_GROUPBY_MONTHS, device_name, start_date,
            groupby_name="groupby_months"
        )

    def getTodayData(self,
                     device_name: str,
                     today: str='now',
                     require_header: bool=True) -> StringIO:
        s_today: str
        if today == 'now':
            s_today = date.today().strftime('%Y-%m-%d')
        else:
            s_today = today
        if self.logger is not None and self.logger_debug:
            self.logger.debug("device_name: {}, today: {}".format(device_name, s_today))

        with self.conn.cursor() as cursor:
            cursor.execute(self._QUERY_TODAY_DATA, {'name': device_name, 'today': s_today})
            tupledlist = cursor.fetchall()
            if self.logger is not None and self.logger_debug:
                self.logger.debug("tupledlist length: {}".format(len(tupledlist)))

        # [tuple, ...] -> StringIO buffer
        return _csvToStringIO(tupledlist, require_header)

    def getMonthData(self,
                     device_name: str,
                     s_year_month: str,
                     require_header: bool=True) -> StringIO:
        s_start = s_year_month + "-01"
        s_end_exclude = nextYearMonth(s_start)
        if self.logger is not None and self.logger_debug:
            self.logger.debug("device_name: {}, from_date: {}, to_next_date: {}".format(
                device_name, s_start, s_end_exclude))

        with self.conn.cursor() as cursor:
            cursor.execute(self._QUERY_RANGE_DATA, {
                    'name': device_name,
                    'from_date': s_start,
                    'to_next_date': s_end_exclude,
                }
            )
            tupledlist = cursor.fetchall()
            if self.logger is not None and self.logger_debug:
                self.logger.debug("tupledlist length: {}".format(len(tupledlist)))

        # [tuple, ...] -> StringIO buffer
        return _csvToStringIO(tupledlist, require_header)

    def getFromToRangeData(self,
                           device_name: str,
                           from_date: str,
                           to_date: str,
                           require_header: bool=True) -> StringIO:
        s_end_exclude: str = addDayToString(to_date)
        if self.logger is not None and self.logger_debug:
            self.logger.debug("device_name: {}, from_date: {}, to_next_date: {}".format(
                device_name, from_date, s_end_exclude))

        with self.conn.cursor() as cursor:
            cursor.execute(self._QUERY_RANGE_DATA, {
                    'name': device_name,
                    'from_date': from_date,
                    'to_next_date': s_end_exclude,
                }
            )
            tupledlist = cursor.fetchall()
            if self.logger is not None and self.logger_debug:
                self.logger.debug("tupledlist length: {}".format(len(tupledlist)))

        # [tuple, ...] -> StringIO buffer
        return _csvToStringIO(tupledlist, require_header)
