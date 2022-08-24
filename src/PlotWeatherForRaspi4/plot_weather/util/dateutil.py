from datetime import datetime, timedelta

FMT_CUSTOM_DATETIME = "%Y-%m-%d %H:%M:%S"
FMT_ISO_8601_DATE = "%Y-%m-%d"
ADD_TIME_00_00_00 = " 00:00:00"
FMT_JP_DATE = "%Y年%m月%d日"
FMT_JP_DATE_WITH_WEEK = "{} ({})"

DICT_DAY_WEEK_JP = {
    "Sun": "日", "Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木", "Fri": "金", "Sat": '土'
}
# datetime.weekday(): 月:0, 火:1, ..., 日:6
LIST_DAY_WEEK_JP = ["月", "火", "水", "木", "金", "土", "日"]


def datetimeToJpDate(cur_datetime):
    return cur_datetime.strftime(FMT_JP_DATE)


def datetimeToJpDateWithWeek(cur_datetime):
    s_date = cur_datetime.strftime(FMT_JP_DATE)
    idx_week = cur_datetime.weekday()
    return FMT_JP_DATE_WITH_WEEK.format(s_date, LIST_DAY_WEEK_JP[idx_week])


def strDateToDatetimeTime000000(s_date):
    return datetime.strptime(s_date + ADD_TIME_00_00_00, FMT_CUSTOM_DATETIME)


def addDayString(s_date, add_days=1, fmt_date=FMT_ISO_8601_DATE):
    dt = datetime.strptime(s_date, fmt_date)
    dt += timedelta(days=add_days)
    s_next = dt.strftime(fmt_date)
    return s_next


def nextYearMonth(s_year_month):
    splited = s_year_month.split('-')
    splited_size = len(splited)
    if splited_size < 2 or splited_size > 3:
        raise ValueError

    year, month = int(splited[0]), int(splited[1])
    month += 1
    if month > 12:
        year += 1
        month = 1
    if splited_size == 2:
        result = f"{year:04}-{month:02}"
    else:
        day = int(splited[2])
        result = f"{year:04}-{month:02}-{day:02}"
    return result
