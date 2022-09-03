import logging
from datetime import date
from io import StringIO

from ..db.sqlite3conv import strdate2timestamp
from ..util.dateutil import addDayToString, nextYearMonth

""" 気象データDAOクラス """

HEADER_WEATHER = '"did","measurement_time","temp_out","temp_in","humid","pressure"'
HEADER_DEVICE = '"id","name"'


class WeatherDao:

    _QUERY_WEATHER_LASTREC = """
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

    _QUERY_GROUPBY_DAYS = """
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

    _QUERY_GROUPBY_MONTHS = """
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

    _QUERY_TODAY_DATA = """
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

    _QUERY_RANGE_DATA = """
SELECT
   did, to_char(measurement_time,'YYYY-MM-DD HH24:MI') measurement_time
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

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        if self.logger is not None:
            self.logger_debug = (self.logger.getEffectiveLevel() <= logging.DEBUG)
        else:
            self.logger_debug = False

    def getLastData(self, device_name):
        """観測デバイスの最終レコードを取得する

        Args:
          device_name str: 観測デバイス名

        Returns:
          tuple: (measurement_time[%Y %m %d %H %M], temp_out, temp_in, humid, pressure)
        """
        with self.conn.cursor() as cursor:
            cursor.execute(self._QUERY_WEATHER_LASTREC, {'name': device_name})
            row = cursor.fetchone()
            if self.logger_debug:
                self.logger.debug("row: {}".format(row))

        return row

    def _getDateGroupByList(self, qrouping_sql, device_name, start_date, groupby_name='groupby_days'):
        """観測デバイスのグルーピングSQLに対応した日付リストを取得する

        Args:
            qrouping_sql str: グルーピングSQL
            device_name str: 観測デバイス名
            start_date str: 検索開始日付
            groupby_name: 'groupby_days' | 'groupby_months'

        Returns:
          list: 文字列の日付 (年月 | 年月日)
        """
        if self.logger_debug:
            self.logger.debug("{}, {}".format(device_name, start_date))
        # Check start_date
        strdate2timestamp(start_date)

        with self.conn.cursor() as cursor:
            cursor.execute(qrouping_sql, {'name': device_name, groupby_name: start_date})
            # fetchall() return tuple list [(?,), (?,), ..., (?,)]
            tupledlist = cursor.fetchall()
            if self.logger_debug:
                self.logger.debug("tupledlist: {}".format(tupledlist))
            # tuple -> list
            result = [item for (item,) in tupledlist]

        return result

    def getGroupbyDays(self, device_name, start_date):
        """観測デバイスの年月日にグルーピングしたリストを取得する

        Args:
            device_name str: 観測デバイス名
            start_date str: 検索開始年月日

        Returns:
            list[str]: 年月日リスト(%Y-%m-%d)
        """
        return self._getDateGroupByList(
            self._QUERY_GROUPBY_DAYS, device_name, start_date, groupby_name="groupby_days"
        )

    def getGroupbyMonths(self, device_name, start_date):
        """観測デバイスの年月にグルーピングしたリストを取得する

        Args:
            device_name str: 観測デバイス名
            start_date str: 検索開始年月日

        Returns:
            list[str]: 降順の年月リスト(%Y-%m)
        """
        return self._getDateGroupByList(
            self._QUERY_GROUPBY_MONTHS, device_name, start_date, groupby_name="groupby_months"
        )

    def _csvToStringIO(self, tupledlist, require_header=True):
        str_buffer = StringIO()
        if require_header:
            str_buffer.write(HEADER_WEATHER+"\n")
          
        for (did, m_time, temp_in, temp_out, humid, pressure) in tupledlist:
            line = f'{did},"{m_time}",{temp_in},{temp_out},{humid},{pressure}\n'
            str_buffer.write(line)
       
        # StringIO need Set first position
        str_buffer.seek(0)
        return str_buffer

    def getTodayData(self, device_name, today='now', require_header=True):
        if today == 'now':
            s_today = date.today().strftime('%Y-%m-%d')
        else:
            s_today = today
        if self.logger_debug:    
            self.logger.debug("device_name: {}, today: {}".format(device_name, s_today))

        with self.conn.cursor() as cursor:
            cursor.execute(self._QUERY_TODAY_DATA, {'name': device_name, 'today': s_today})
            tupledlist = cursor.fetchall()
            if self.logger_debug:
                self.logger.debug("tupledlist length: {}".format(len(tupledlist)))

        # [tuple, ...] -> StringIO buffer
        return self._csvToStringIO(tupledlist, require_header)

    def getMonthData(self, device_name, s_year_month, require_header=True):
        s_start = s_year_month + "-01"
        s_end_exclude = nextYearMonth(s_start)
        if self.logger_debug:
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
            if self.logger_debug:
                self.logger.debug("tupledlist length: {}".format(len(tupledlist)))

        # [tuple, ...] -> StringIO buffer
        return self._csvToStringIO(tupledlist, require_header)

    def getFromToRangeData(self, device_name, from_date, to_date, require_header=True):
        s_end_exclude = addDayToString(to_date)
        if self.logger_debug:
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
            if self.logger_debug:
                self.logger.debug("tupledlist length: {}".format(len(tupledlist)))

        # [tuple, ...] -> StringIO buffer
        return self._csvToStringIO(tupledlist, require_header)
