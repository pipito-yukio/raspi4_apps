from datetime import datetime, timedelta
from typing import Dict, List

FMT_CUSTOM_DATETIME: str = "%Y-%m-%d %H:%M:%S"
FMT_ISO_8601_DATE: str = "%Y-%m-%d"
ADD_TIME_00_00_00: str = " 00:00:00"
FMT_JP_DATE: str = "%Y年%m月%d日"
FMT_JP_DATE_WITH_WEEK: str = "{} ({})"

DICT_DAY_WEEK_JP: Dict[str, str] = {
    "Sun": "日", "Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木", "Fri": "金", "Sat": '土'
}
# datetime.weekday(): 月:0, 火:1, ..., 日:6
LIST_DAY_WEEK_JP: List[str] = ["月", "火", "水", "木", "金", "土", "日"]


def datetimeToJpDate(curc_datetime: datetime) -> str:
    """
    datetimeを日本語日付に変換する
    param: cur_datetime
    :return: 日本語日付
    """
    return curc_datetime.strftime(FMT_JP_DATE)


def datetimeToJpDateWithWeek(cur_datetime: datetime) -> str:
    """
    日本語の曜日を含む日付を返却する
    (例) 2022-09-09 -> 2022-09-09 (金)
    :param currDatetime:日付
    :return: 日本語の曜日を含む日付
    """
    s_date: str = cur_datetime.strftime(FMT_JP_DATE)
    idx_week: int = cur_datetime.weekday()
    return FMT_JP_DATE_WITH_WEEK.format(s_date, LIST_DAY_WEEK_JP[idx_week])


def strDateToDatetimeTime000000(s_date: str) -> datetime:
    """
    日付文字列の "00:00:00"のdatetimeブジェクトを返却する
    :param strDate: 日付文字列
    :return: datetimeブジェクト
    """
    return datetime.strptime(s_date + ADD_TIME_00_00_00, FMT_CUSTOM_DATETIME)


def addDayToString(
        s_date: str,
        add_days: int = 1,
        dateFormatter: str = FMT_ISO_8601_DATE) -> str:
    """
    日付文字列に加算日数を加えた日付文字列を出力日付書式に従って返却する
    (例) '2022-08-30' + 2日 -> '2022-09-01'
    :param s_date: 日付文字列
    :param add_days: 加算日数 ※マイナス日数の場合
    :param dateFormatter: 出力日付書式
    :return: 出力日付書式の加算日付文字列
    """
    dt:datetime = datetime.strptime(s_date, dateFormatter)
    dt += timedelta(days=add_days)
    s_next: str = dt.strftime(dateFormatter)
    return s_next


def nextYearMonth(s_year_month: str) -> str:
    """
    年月文字列の次の月を計算する
    :param s_year_month: 年月文字列
    :return: 翌年月叉は翌年月日
    :raise ValueError:
    """
    date_parts: List[str] = s_year_month.split('-')
    date_parts_size = len(date_parts)
    if date_parts_size < 2 or date_parts_size > 3:
        raise ValueError

    year, month = int(date_parts[0]), int(date_parts[1])
    month += 1
    if month > 12:
        year += 1
        month = 1
    if date_parts_size == 2:
        result = f"{year:04}-{month:02}"
    else:
        day = int(date_parts[2])
        result = f"{year:04}-{month:02}-{day:02}"
    return result
