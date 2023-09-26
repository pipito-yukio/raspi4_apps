import base64
import enum
import logging
from typing import Dict, List, Optional, Tuple, Union
from datetime import date, datetime, timedelta
from io import BytesIO
from io import StringIO

from ..dao.weathercommon import PLOT_CONF
from psycopg2.extensions import connection
import pandas as pd
import matplotlib.dates as mdates
from matplotlib import rcParams

# 日本語フォントの設定方法
#  日本語フォントとしてIPAexフォントがインストール済みのであると仮定した場合
# [A] 叉は [B] のどちらの方法でも指定された日本語フォントが反映される
# [A] https://matplotlib.org/3.1.0/gallery/text_labels_and_annotations/font_family_rc_sgskip.html
#    Configuring the font family
# rcParams['font.family'] = 'sans-serif'
# rcParams[font.sans-serif] = ['IPAexGothic'] <<-- リスト
# ~/[Application root]/plot_weather/dao/conf/plot_weather.json: PLOT_CONF
rcParams['font.family'] = PLOT_CONF['font.family']
font_family_font: str = 'font.' + PLOT_CONF['font.family']
rcParams[font_family_font] = PLOT_CONF['japanese.font']
# [B] "matplotlibrc" ファイルの 14,15,16行目に記載されている方法
# ## If you wish to change your default style, copy this file to one of the
# ## following locations:
# ##     Unix/Linux:
# ##            $HOME/.config/matplotlib/matplotlibrc
# ## ...無関係部分省略...
# ## and edit that copy.
# 下記(1),(2)のコメントアウトを外す ※オリジナルはコメントアウトされている
#  (1) font.family: sans-serif
#      "IPAexGothic" を先頭に追記する
#  (2) font.sans-serif: IPAexGothic, DejaVu Sans, ..., sans-serif
from matplotlib.figure import Figure
from matplotlib.pyplot import setp
from matplotlib import axes

from ..dao.weatherdao import WeatherDao
from ..util.dateutil import (addDayToString, datetimeToJpDateWithWeek,
                             strDateToDatetimeTime000000,
                             FMT_ISO_8601_DATE, FMT_CUSTOM_DATETIME
                             )

""" 気象データ画像のbase64エンコードテキストデータを出力する """

# pandas.DataFrameのインデックス列
WEATHER_IDX_COLUMN: str = 'measurement_time'
# クラフの軸ラベルフォントサイズ
LABEL_FONT_SIZE: int = 10
# グラフのグリッド線スタイル
GRID_STYLES: Dict[str, Union[str, float]] = {"linestyle": "- -", "linewidth": 1.0}


class ImageDateType(enum.Enum):
    """ 日付データ型 """
    TODAY = 0      # 当日データ
    YEAR_MONTH = 1 # 年月データ
    RANGE = 2      # 期間データ: 当日を含む過去日(検索開始日)からN日後


class ParamKey(enum.Enum):
    TODAY = "today"
    YEAR_MONTH = "yearMonth"
    BEFORE_DAYS = "beforeDays"
    START_DAY = "startDay"
    PHONE_SIZE = "phoneSize"


class ImageDateParams(object):
    def __init__(self, imageDateType: ImageDateType = ImageDateType.TODAY):
        self.imageDateType = imageDateType
        self.typeParams: Dict[ImageDateType, Dict[ParamKey, str]] = {
            ImageDateType.TODAY: {ParamKey.TODAY: "", ParamKey.PHONE_SIZE: ""},
            ImageDateType.YEAR_MONTH: {ParamKey.YEAR_MONTH: ""},
            ImageDateType.RANGE: {
                ParamKey.START_DAY: "",
                ParamKey.BEFORE_DAYS: "",
                ParamKey.PHONE_SIZE: ""
            }
        }

    def getParam(self) -> Dict[ParamKey, str]:
        return self.typeParams[self.imageDateType]

    def setParam(self, param: Dict[ParamKey, str]):
        self.typeParams[self.imageDateType] = param

    def getImageDateType(self) -> ImageDateType:
        return self.imageDateType


def _to_japanese_date(s_date: str) -> str:
    """
    ISO8601日付文字列を日本語日付に変換
    :param s_date: ISO8601日付文字列
    :return 日本語日付
    """
    date_parts: List[str] = s_date.split("-")
    return f"{date_parts[0]}年{date_parts[1]}月{date_parts[2]}日"


def loadTodayDataFrame(
        dao: WeatherDao, device_name: str, today_iso8601: str,
        logger: Optional[Optional[logging.Logger]] = None, logger_debug: bool = False
) -> Tuple[int, Optional[pd.DataFrame], Optional[str], Optional[datetime], Optional[datetime]]:
    # dao return StringIO buffer(line'\n') on csv format with header
    rec_count: int
    csv_buffer: StringIO
    rec_count, csv_buffer = dao.getTodayData(device_name, today_iso8601, require_header=True)
    # 件数なし
    if rec_count == 0:
        return rec_count, None, None, None, None

    df: pd.DataFrame = pd.read_csv(
        csv_buffer,
        header=0,
        parse_dates=[WEATHER_IDX_COLUMN],
        names=[WEATHER_IDX_COLUMN, 'temp_out', 'temp_in', 'humid', 'pressure']  # Use cols
    )
    if logger is not None and logger_debug:
        logger.debug(f"Before df:\n{df}")
        logger.debug(f"Before df.index:\n{df.index}")

    # タイムスタンプをデータフレームのインデックスに設定
    #  df.index: RangeIndex(start=0, stop=70, step=1) ※行番号 (0..)
    #   drop=False: "measurement_time"列をDataFrameに残す
    #   inplace=True: オリジナルのDataFrameのインデックスを"measurement_time"列にする
    #   inplace=False: オリジナルのインデックスは更新されず、更新されたコピーが返却される
    #    df = df.set_index(WEATHER_IDX_COLUMN)  とする必要がある
    df.set_index(WEATHER_IDX_COLUMN, drop=False, inplace=True)
    if logger is not None and logger_debug:
        logger.debug(f"After df:\n{df}")
        logger.debug(f"After df.index:\n{df.index}")
    if not df.empty:
        # 先頭の測定日付(Pandas Timestamp) から Pythonのdatetimeに変換
        # https://pandas.pydata.org/pandas-docs/version/0.22/generated/pandas.Timestamp.to_datetime.html
        first_datetime = df.index[0].to_pydatetime()
    else:
        # No data: Since the broadcast of observation data is every 10 minutes,
        #          there may be cases where there is no data at the time of execution.
        first_datetime = datetime.now()
    # 当日の日付文字列 ※一旦 dateオブジェクトに変換して"年月日"を取得
    s_first_date: str = first_datetime.date().isoformat()
    # 表示範囲：当日の "00:00:00" から
    x_day_min: datetime = strDateToDatetimeTime000000(s_first_date)
    # 翌日の "00:00:00" 迄
    s_nextday: str = addDayToString(s_first_date)
    x_day_max: datetime = strDateToDatetimeTime000000(s_nextday)
    # タイトル用の日本語日付(曜日)
    s_title_date: str = datetimeToJpDateWithWeek(first_datetime)
    return rec_count, df, s_title_date, x_day_min, x_day_max


def loadMonthDataFrame(
        dao: WeatherDao, device_name: str, year_month: str = "",
        logger: Optional[logging.Logger] = None, logger_debug: bool = False
) -> Tuple[int, Optional[pd.DataFrame], Optional[str]]:
    rec_count: int
    csv_buffer: StringIO
    rec_count, csv_buffer = dao.getMonthData(device_name, year_month,
                                             require_header=True)
    # 件数なし
    if rec_count == 0:
        return rec_count, None, None

    # タイムスタンプをデータフレームのインデックスに設定
    df: pd.DataFrame = pd.read_csv(
        csv_buffer,
        header=0,
        parse_dates=[WEATHER_IDX_COLUMN],
        names=[WEATHER_IDX_COLUMN, 'temp_out', 'temp_in', 'humid', 'pressure']
    )
    if logger is not None and logger_debug:
        logger.debug(df)

    # タイムスタンプをデータフレームのインデックスに設定
    df.set_index(WEATHER_IDX_COLUMN, drop=False, inplace=True)
    # タイトル用の日本語日付(曜日)
    date_parts: List[str] = year_month.split("-")
    s_title_date = f"{date_parts[0]}年{date_parts[1]}月"
    return rec_count, df, s_title_date


def loadBeforeDaysRangeDataFrame(
        dao: WeatherDao, device_name: str,
        s_start_day: str,
        before_days: int,
        logger: Optional[logging.Logger] = None, logger_debug: bool = False
) -> Tuple[int, Optional[pd.DataFrame], Optional[str]]:
    start_day: datetime = datetime.strptime(s_start_day, FMT_ISO_8601_DATE)
    from_date_val: datetime = start_day - timedelta(days=before_days)
    s_from_date: str = from_date_val.strftime(FMT_ISO_8601_DATE)
    s_to_date: str = start_day.strftime(FMT_ISO_8601_DATE)
    if logger is not None and logger_debug:
        logger.debug(f"from_date: {s_from_date}, to_date: {s_from_date}")
    rec_count: int
    csv_buffer: StringIO
    rec_count, csv_buffer = dao.getFromToRangeData(
        device_name, s_from_date, s_to_date, require_header=True)
    # 件数なし
    if rec_count == 0:
        return rec_count, None, None

    # タイムスタンプをデータフレームのインデックスに設定
    df: pd.DataFrame = pd.read_csv(
        csv_buffer,
        header=0,
        parse_dates=[WEATHER_IDX_COLUMN],
        names=[WEATHER_IDX_COLUMN, 'temp_out', 'temp_in', 'humid', 'pressure']
    )
    if logger is not None and logger_debug:
        logger.debug(df)

    # タイムスタンプをデータフレームのインデックスに設定
    df.set_index(WEATHER_IDX_COLUMN, drop=False, inplace=True)
    # タイトル用の日本語日付: from_date 〜 to_date
    s_from_date = _to_japanese_date(s_from_date)
    s_to_date = _to_japanese_date(s_to_date)
    s_title_date: str = f"{s_from_date} 〜 {s_to_date}"
    return rec_count, df, s_title_date


def _temperaturePlotting(
        ax: axes.Axes, df: pd.DataFrame, titleDate: str, labelFontSize: int) -> None:
    """
    温度サブプロット(axes)にタイトル、軸・軸ラベルを設定し、
    DataFrameオプジェクトの外気温・室内気温データをプロットする
    :param ax:温度サブプロット(axes)
    :param df:DataFrameオプジェクト
    :param titleDate: タイトル日付文字列
    :param labelFontSize: ラベルフォントサイズ
    """
    ax.plot(df[WEATHER_IDX_COLUMN], df["temp_out"], color="blue", marker="", label="外気温")
    ax.plot(df[WEATHER_IDX_COLUMN], df["temp_in"], color="red", marker="", label="室内気温")
    ax.set_ylim(PLOT_CONF["ylim"]["temp"])
    ax.set_ylabel("気温 (℃)", fontsize=labelFontSize)
    ax.legend(loc="best")
    ax.set_title(f"気象データ：{titleDate}")
    # Hide xlabel
    ax.label_outer()
    ax.grid(GRID_STYLES)


def _humidPlotting(ax: axes.Axes, df: pd.DataFrame, labelFontSize) -> None:
    """
    湿度サブプロット(axes)に軸・軸ラベルを設定し、DataFrameオプジェクトの室内湿度データをプロットする
    :param ax:湿度サブプロット(axes)
    :param df:DataFrameオプジェクト
    :param labelFontSize: ラベルフォントサイズ
    """
    ax.plot(df[WEATHER_IDX_COLUMN], df["humid"], color="green", marker="")
    ax.set_ylim([0, 100])
    ax.set_ylabel("室内湿度 (％)", fontsize=labelFontSize)
    # Hide xlabel
    ax.label_outer()
    ax.grid(GRID_STYLES)


def _pressurePlotting(ax: axes.Axes, df: pd.DataFrame, labelFontSize: int) -> None:
    """
    気圧サブプロット(axes)に軸・軸ラベルを設定し、DataFrameオプジェクトの気圧データをプロットする
    :param ax:気圧サブプロット(axes)
    :param df:DataFrameオプジェクト
    :param labelFontSize: ラベルフォントサイズ
    """
    ax.plot(df[WEATHER_IDX_COLUMN], df["pressure"], color="fuchsia", marker="")
    ax.set_ylim(PLOT_CONF["ylim"]["pressure"])
    ax.set_ylabel("hPa", fontsize=labelFontSize)
    ax.grid(GRID_STYLES)


def _axesPressureSettingWithBeforeDays(
        ax: axes.Axes, start_day: str, beforeDays: int, xDateTickFontSize: int) -> None:
    """
    気圧サブプロットの期間指定x軸ラベルを設定する
    :param ax:気圧サブプロット(axes)
    :param start_day: 検索日 ※本日以外にアプリから過去の任意の日付を指定可能
    :param beforeDays: 当日からＮ日前のＮ
    :param xDateTickFontSize: 日付軸ラベルフォントサイズ
    """
    # datetimeオブジェタクトに変更
    start_datetime: datetime = datetime.strptime(start_day, FMT_ISO_8601_DATE)
    # デフォルトでは最後の軸に対応する日付ラベルが表示されない
    # 次の日の 00:30 までラベルを表示するための日付計算
    next_day: datetime = start_datetime + timedelta(days=1)
    s_next_day: str = next_day.strftime("%Y-%m-%d 00:30:00")
    # datetimeオブジェクトに戻す
    next_day = datetime.strptime(s_next_day, FMT_CUSTOM_DATETIME)
    ax.set_xlim(xmax=next_day)
    if beforeDays == 7:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.tick_params(axis='x', labelsize=xDateTickFontSize - 1)
    else:
        # [1,2,3] day
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        ax.tick_params(axis='x', labelsize=xDateTickFontSize - 1, labelrotation=45)


def gen_plot_image(
        conn: connection, device_name: str, image_params: ImageDateParams, logger=None
) -> Tuple[int, Optional[str]]:
    # for ImageDateType.TODAY
    global x_day_min, x_day_max
    # for ImageDateType.RANGE
    global s_start_day, before_days
    if logger is not None:
        logger_debug = (logger.getEffectiveLevel() <= logging.DEBUG)
    else:
        logger_debug = False

    dao = WeatherDao(conn, logger=logger)
    s_phone_size: str = ""
    if image_params.getImageDateType() == ImageDateType.TODAY:
        param: Dict[ParamKey, str] = image_params.getParam()
        s_phone_size = param.get(ParamKey.PHONE_SIZE, "")
        # app_mainで当日が設定される
        s_today: str = param.get(ParamKey.TODAY, "")
        if logger is not None and logger_debug:
            logger.debug(f"today: {s_today}, phone_size: {s_phone_size}")
        rec_count, df, title_date, x_day_min, x_day_max = loadTodayDataFrame(
            dao, device_name, s_today, logger=logger, logger_debug=logger_debug
        )
    elif image_params.getImageDateType() == ImageDateType.YEAR_MONTH:
        # 指定された年月データ
        param: Dict[ParamKey, str] = image_params.getParam()
        s_year_month: str = param.get(ParamKey.YEAR_MONTH, "")
        if logger is not None and logger_debug:
            logger.debug(f"s_year_month: {s_year_month}")
        rec_count, df, title_date = loadMonthDataFrame(
            dao, device_name, year_month=s_year_month, logger=logger, logger_debug=logger_debug
        )
    else:
        # 範囲指定データ
        param: Dict[ParamKey, str]  = image_params.getParam()
        # [仕様変更] 検索開始日 (start_day)
        s_start_day = param.get(ParamKey.START_DAY, "")
        s_before_days = param.get(ParamKey.BEFORE_DAYS, "")
        s_phone_size = param.get(ParamKey.PHONE_SIZE, "")
        if logger is not None and logger_debug:
            logger.debug(f"start_day: {s_start_day}, before_days: {s_before_days}")
        before_days = int(s_before_days)
        rec_count, df, title_date = loadBeforeDaysRangeDataFrame(
            dao, device_name, s_start_day, before_days,
            logger=logger, logger_debug=logger_debug
        )
    # 件数チェック
    if rec_count == 0:
        return rec_count, None

    # 図の生成
    if s_phone_size is not None and len(s_phone_size) > 8:
        sizes: List[str] = s_phone_size.split("x")
        widthPixel: int = int(sizes[0])
        heightPixel: int = int(sizes[1])
        density: float = float(sizes[2])
        # Androidスマホは pixel指定
        # https://matplotlib.org/stable/gallery/subplots_axes_and_figures/figure_size_units.html
        #   Figure size in pixel
        px: float = 1 / rcParams["figure.dpi"]  # pixel in inches
        # density=1.0 の10インチタブレットはちょうどいい
        # 画面の小さいスマホのdensityで割る ※densityが大きい端末だとグラフサイズが極端に小さくなる
        #  いまのところ Pixel-4a ではこれが一番綺麗に表示される
        px = px / (2.0 if density > 2.0 else density)
        fig_width_px: float = widthPixel * px
        fig_height_px: float = heightPixel * px
        if logger is not None and logger_debug:
            logger.debug(f"px: {px} / density : {density}")
            logger.debug(f"fig_width_px: {fig_width_px}, fig_height_px: {fig_height_px}")
        fig = Figure(figsize=(fig_width_px, fig_height_px), constrained_layout=True)
    else:
        # PCブラウザはinch指定
        fig = Figure(figsize=PLOT_CONF["figsize"]["pc"], constrained_layout=True)
    if logger is not None and logger_debug:
        logger.debug(f"fig: {fig}")

    # x軸を共有する3行1列のサブプロット生成
    (ax_temp, ax_humid, ax_pressure) = fig.subplots(3, 1, sharex=True)

    # 軸ラベルのフォントサイズを設定
    #  ラベルフォントサイズ, y軸ラベルフォントサイズ, x軸(日付)ラベルフォントサイズ
    labelFontSize: int = PLOT_CONF["label.sizes"][0]
    yTickLabelsFontSize: int = PLOT_CONF["label.sizes"][1]
    dateTickLablesFontSize: int = PLOT_CONF["label.sizes"][2]
    for ax in [ax_temp, ax_humid, ax_pressure]:
        setp(ax.get_xticklabels(), fontsize=dateTickLablesFontSize)
        setp(ax.get_yticklabels(), fontsize=yTickLabelsFontSize)

    # サブプロットの設定
    # 1.外気温と室内気温
    _temperaturePlotting(ax_temp, df, title_date, labelFontSize)
    # 2.室内湿度
    _humidPlotting(ax_humid, df, labelFontSize)
    # 3.気圧
    if image_params.getImageDateType() == ImageDateType.TODAY:
        # 当日データx軸の範囲: 当日 00時 から 翌日 00時
        for ax in [ax_temp, ax_humid, ax_pressure]:
            ax.set_xlim([x_day_min, x_day_max])
        # 当日データのx軸フォーマット: 軸ラベルは時間 (00,03,06,09,12,15,18,21,翌日の00)
        ax_pressure.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
    elif image_params.getImageDateType() == ImageDateType.YEAR_MONTH:
        # 年月指定データのx軸フォーマット設定: 軸は"月/日"
        ax_pressure.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    else:
        # 期間データのx軸フォーマット設定
        _axesPressureSettingWithBeforeDays(
            ax_pressure, s_start_day, before_days, dateTickLablesFontSize
        )
    # 気圧データプロット
    _pressurePlotting(ax_pressure, df, labelFontSize)

    # 画像をバイトストリームに溜め込みそれをbase64エンコードしてレスポンスとして返す
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    data = base64.b64encode(buf.getbuffer()).decode("ascii")
    if logger is not None and logger_debug:
        logger.debug(f"data.len: {len(data)}")
    img_src = "data:image/png;base64," + data
    # 件数と画像
    return rec_count, img_src
