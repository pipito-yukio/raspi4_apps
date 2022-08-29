import base64
import enum
import logging
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
from matplotlib import rcParams
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.pyplot import setp

from ..dao.weathercommon import PLOT_CONF, WEATHER_CONF
from ..dao.weatherdao import WeatherDao
from ..util.dateutil import (addDayToString, datetimeToJpDateWithWeek,
                             strDateToDatetimeTime000000, FMT_ISO_8601_DATE)

""" 気象データ画像のbase64エンコードテキストデータを出力する """

# 日本語フォント設定
# https://matplotlib.org/3.1.0/gallery/text_labels_and_annotations/font_family_rc_sgskip.html
rcParams["font.family"] = PLOT_CONF["font.family"]


# 日付画像型Enum
class ImageDateType(enum.Enum):
    TODAY = 0
    YEAR_MONTH = 1
    RANGE = 2


WEATHER_IDX_COLUMN = 'measurement_time'
fig=None

def gen_plot_image(conn, width_pixel=None, height_pixel=None, density=None,
                   image_date_type=ImageDateType.TODAY, date_value=None, logger=None):
    if logger is not None:
        logger_debug = (logger.getEffectiveLevel() <= logging.DEBUG)
    else:
        logger_debug = False

    dao = WeatherDao(conn, logger=logger)
    if image_date_type == ImageDateType.TODAY:
        # 本日データ: "now" or 過去("YYYY-MM-DD")
        df, title_date, x_day_min, x_day_max = loadTodayDataFrame(
            dao, logger=logger, logger_debug=logger_debug)
    elif image_date_type == ImageDateType.YEAR_MONTH:
        # 指定された年月データ
        df, title_date = loadMonthDataFrame(
            dao, year_month=date_value, logger=logger, logger_debug=logger_debug)
    elif image_date_type == ImageDateType.RANGE:
        # date_value is beforedays
        df, title_date = loadBeforeDaysRangeDataFrame(
            dao, date_value, logger=logger, logger_debug=logger_debug)

    # https://matplotlib.org/stable/api/figure_api.html?highlight=figure#module-matplotlib.figure
    if width_pixel is not None and height_pixel is not None:
        # https://matplotlib.org/stable/gallery/subplots_axes_and_figures/figure_size_units.html
        #   Figure size in pixel
        px = 1 / rcParams["figure.dpi"]  # pixel in inches
        # density=1.0 の10インチタブレットはちょうどいい
        # 画面の小さいスマホのdensityで割る ※densityが大きい端末だとグラフサイズが極端に小さくなる
        #  いまのところ Pixel-4a ではこれが一番綺麗に表示される
        px = px / (2.0 if density > 2.0 else density)
        fig_width_px, fig_height_px = width_pixel * px, height_pixel * px
        if logger_debug:
            logger.debug(f"px: {px} / density : {density}")
            logger.debug(f"fig_width_px: {fig_width_px}, fig_height_px: {fig_height_px}")
        fig = Figure(figsize=(fig_width_px, fig_height_px))
    else:
        fig = Figure(figsize=PLOT_CONF["figsize"]["pc"])

    if logger_debug:
        logger.debug(f"fig: {fig}")
    label_fontsize, ticklabel_fontsize, ticklable_date_fontsize = tuple(
        PLOT_CONF["label.sizes"]
    )

    grid_styles = {"linestyle": "- -", "linewidth": 1.0}
    # PC用
    # TypeError: subplots() got an unexpected keyword argument 'constrained_layout'
    (ax_temp, ax_humid, ax_pressure) = fig.subplots(3, 1, sharex=True)

    # サブプロット間の間隔を変更する
    # Figure(..., constrained_layout=True) と subplots_adjust()は同時に設定できない
    # UserWarning: This figure was using constrained_layout,
    #  but that is incompatible with subplots_adjust and/or tight_layout; disabling constrained_layout.
    fig.subplots_adjust(wspace=0.1, hspace=0.1)
    # 軸ラベルなどのフォントサイズを設定
    for ax in [ax_temp, ax_humid, ax_pressure]:
        setp(ax.get_xticklabels(), fontsize=ticklable_date_fontsize)
        setp(ax.get_yticklabels(), fontsize=ticklabel_fontsize)

    if image_date_type == ImageDateType.TODAY:
        # 1日データx軸の範囲: 当日 00時 から 翌日 00時
        for ax in [ax_temp, ax_humid, ax_pressure]:
            ax.set_xlim([x_day_min, x_day_max])

    # temp_out and temp_in
    _axesTemperatureSetting(
        ax_temp, df,
        labelFontSize=label_fontsize, titleDate=title_date, gridStyles=grid_styles
    )
    # humid
    _axesHumidSetting(
        ax_humid, df, labelFontSize=label_fontsize, gridStyles=grid_styles
    )
    # pressure
    _axesPressureSetting(
        ax_pressure, df, labelFontSize=label_fontsize, gridStyles=grid_styles,
        image_date_type=image_date_type, before_days=date_value
    )

    # 画像をバイトストリームに溜め込みそれをbase64エンコードしてレスポンスとして返す
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    data = base64.b64encode(buf.getbuffer()).decode("ascii")
    if logger_debug:
        logger.debug(f"data.len: {len(data)}")
    img_src = "data:image/png;base64," + data
    return img_src


def loadTodayDataFrame(dao, logger=None, logger_debug=False):
    s_today = WEATHER_CONF["TODAY"]
    # dao return StringIO buffer(line'\n') on csv format with header
    csv_buffer = dao.getTodayData(WEATHER_CONF["DEVICE_NAME"], today=s_today, require_header=True)
    df = pd.read_csv(csv_buffer,
                     header=0,
                     parse_dates=[WEATHER_IDX_COLUMN],
                     names=[WEATHER_IDX_COLUMN, 'temp_out', 'temp_in', 'humid', 'pressure']
                     )
    if logger_debug:
        logger.debug(f"df: {df}")
    # タイムスタンプをデータフレームのインデックスに設定
    df.index = df[WEATHER_IDX_COLUMN]
    if not df.empty:
        # 先頭の測定日付(Pandas Timestamp) から Pythonのdatetimeに変換
        # https://pandas.pydata.org/pandas-docs/version/0.22/generated/pandas.Timestamp.to_datetime.html
        first_datetime = df.index[0].to_pydatetime()
    else:
        # No data: Since the broadcast of observation data is every 10 minutes,
        #          there may be cases where there is no data at the time of execution.
        if s_today == "now":
            first_datetime = datetime.now()
        else:
            first_datetime = datetime.strptime(s_today, "%Y-%m-%d")
    # 当日の日付文字列 ※一旦 dateオブジェクトに変換して"年月日"を取得
    s_first_date = first_datetime.date().isoformat()
    # 表示範囲：当日の "00:00:00" から
    x_day_min = strDateToDatetimeTime000000(s_first_date)
    # 翌日の "00:00:00" 迄
    s_nextday = addDayToString(s_first_date)
    x_day_max = strDateToDatetimeTime000000(s_nextday)
    # タイトル用の日本語日付(曜日)
    s_title_date = datetimeToJpDateWithWeek(first_datetime)
    return df, s_title_date, x_day_min, x_day_max


def loadMonthDataFrame(dao, year_month=None, logger=None, logger_debug=False):
    csv_buffer = dao.getMonthData(WEATHER_CONF["DEVICE_NAME"], year_month, require_header=True)
    # タイムスタンプをデータフレームのインデックスに設定
    df = pd.read_csv(csv_buffer,
                     header=0,
                     parse_dates=[WEATHER_IDX_COLUMN],
                     names=[WEATHER_IDX_COLUMN, 'temp_out', 'temp_in', 'humid', 'pressure']
                     )
    if logger_debug:
        logger.debug(df)
    df.index = df[WEATHER_IDX_COLUMN]
    # タイトル用の日本語日付(曜日)
    splited = year_month.split("-")
    s_title_date = f"{splited[0]}年{splited[1]}月"
    return df, s_title_date


def loadBeforeDaysRangeDataFrame(dao, before_days, logger=None, logger_debug=False):
    today = datetime.today()
    from_date = today - timedelta(days=before_days)
    from_date = from_date.strftime(FMT_ISO_8601_DATE)
    to_date = today.strftime(FMT_ISO_8601_DATE)
    csv_buffer = dao.getFromToRangeData(
        WEATHER_CONF["DEVICE_NAME"], from_date, to_date, require_header=True)
    # タイムスタンプをデータフレームのインデックスに設定
    df = pd.read_csv(csv_buffer,
                     header=0,
                     parse_dates=[WEATHER_IDX_COLUMN],
                     names=[WEATHER_IDX_COLUMN, 'temp_out', 'temp_in', 'humid', 'pressure']
                     )
    if logger_debug:
        logger.debug(df)
    df.index = df[WEATHER_IDX_COLUMN]
    # タイトル用の日本語日付: 2022年08月10日〜今日
    splited = from_date.split("-")
    s_title_date = f"{splited[0]}年{splited[1]}月{splited[2]}日〜今日"
    return df, s_title_date


def _axesTemperatureSetting(ax, df, labelFontSize=None, titleDate=None, gridStyles=None):
    ax.plot(
        df[WEATHER_IDX_COLUMN], df["temp_out"], color="blue", marker="", label="外気温",
    )
    ax.plot(
        df[WEATHER_IDX_COLUMN], df["temp_in"], color="red", marker="", label="室内気温"
    )
    ax.set_ylim(PLOT_CONF["ylim"]["temp"])
    ax.set_ylabel("気温 (℃)", fontsize=labelFontSize)
    ax.legend(loc="best")
    ax.set_title("気象データ：{}".format(titleDate))
    # Hide xlabel
    ax.label_outer()
    ax.grid(gridStyles)


def _axesHumidSetting(ax, df, labelFontSize=None, gridStyles=None):
    ax.plot(df[WEATHER_IDX_COLUMN], df["humid"], color="green", marker="")
    ax.set_ylim([0, 100])
    ax.set_ylabel("室内湿度 (％)", fontsize=labelFontSize)
    # Hide xlabel
    ax.label_outer()
    ax.grid(gridStyles)


def _axesPressureSetting(ax, df, labelFontSize=None, gridStyles=None,
                         image_date_type=ImageDateType.TODAY, before_days=1):
    global fig
    # リクエストの画像データ型によって軸が変わる
    if image_date_type == ImageDateType.TODAY:
        # 当日データなので軸ラベルは時間 (00,03,06,09,12,15,18,21,翌日の00)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
    elif image_date_type == ImageDateType.YEAR_MONTH:
        # 年月指定なので軸は"月/日"
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    elif image_date_type == ImageDateType.RANGE:
        # デフォルトでは最後の軸に対応する日付ラベルが表示されない
        # 次の日の 00:30 までラベルを表示するための日付計算
        today = datetime.today()
        next_day = today + timedelta(days=1)
        next_day = next_day.strftime("%Y-%m-%d 00:30:00")
        # datetimeオブジェクトとに戻す
        next_day = datetime.strptime(next_day, "%Y-%m-%d %H:%M:%S")
        ax.set_xlim(xmax=next_day)
        if before_days == 7:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            # https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.tick_params.html
            ax.tick_params(axis='x', labelsize=8.0)
        else:
            # [1,2,3] day
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
            ax.tick_params(axis='x', labelsize=8.0, labelrotation=45)

    ax.plot(
        df[WEATHER_IDX_COLUMN], df["pressure"], color="fuchsia", marker=""
    )
    ax.set_ylim(PLOT_CONF["ylim"]["pressure"])
    ax.set_ylabel("hPa", fontsize=labelFontSize)
    ax.grid(gridStyles)
