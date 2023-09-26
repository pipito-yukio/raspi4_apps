from datetime import datetime

"""
Conversion utilities for SQLite3.
"""

TIME_FORMAT_DATE = "%Y-%m-%d"
TIME_FORMAT_DATETIME = TIME_FORMAT_DATE + " %H:%M:%S"


class DateFormatError(ValueError):
    """ Date format exception for SQL """
    DEFAULT_MESSAGE = "{} is not Date"

    def __init__(self, date_str, message=None, filed_name=None):
        if message is not None:
            self.message = message
        else:
            self.message = self.DEFAULT_MESSAGE.format(date_str)
        super().__init__(self.message)
        self.field_name = filed_name


def strdate2timestamp(date_str, raise_error=False):
    """
    Date string convert to unix timestamp
    :param date_str: Date string ('YYYY-mm-dd')
    :param raise_error if True then except ValueError raise DateFormatError else return None
    :return: unix timestamp or None
    :exception DateFormatError
    """
    try:
        ts = datetime.strptime(date_str, TIME_FORMAT_DATE)
    except ValueError as e:
        if raise_error:
            raise DateFormatError(date_str)
        else:
            ts = None
    return ts


def to_float(s_value):
    """
    Numeric string convert to float value
    :param s_value: Numeric string
    :return: float value or if ValueError, None
    """
    try:
        val = float(s_value)
    except ValueError:
        val = None
    return val
