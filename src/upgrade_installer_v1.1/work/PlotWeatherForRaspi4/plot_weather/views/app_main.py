from datetime import date
from typing import Dict, List, Optional, Tuple, Union

from flask import (
    abort, g, jsonify, render_template, request, make_response, Response
)
from werkzeug.exceptions import (
    BadRequest, Forbidden, HTTPException, InternalServerError, NotFound
    )
from plot_weather import (BAD_REQUEST_IMAGE_DATA,
                          INTERNAL_SERVER_ERROR_IMAGE_DATA, DebugOutRequest,
                          app, app_logger, app_logger_debug)
from plot_weather.dao.weathercommon import WEATHER_CONF
from plot_weather.dao.weatherdao import WeatherDao
from plot_weather.dao.devicedao import DeviceDao, DeviceRecord
from plot_weather.db.sqlite3conv import DateFormatError, strdate2timestamp
from plot_weather.plotter.plotterweather import (
    ImageDateType, gen_plot_image, ImageDateParams, ParamKey
)
from werkzeug.datastructures import Headers, MultiDict
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extensions import connection
import plot_weather.util.dateutil as date_util

APP_ROOT: str = app.config["APPLICATION_ROOT"]

# エラーメッセージの内容 ※messages.confで定義
MSG_REQUIRED: str = app.config["MSG_REQUIRED"]
MSG_INVALID: str = app.config["MSG_INVALID"]
MSG_NOT_FOUND: str = app.config["MSG_NOT_FOUND"]
# ヘッダー
# トークン ※携帯端末では必須, 一致 ※ない場合は不一致とみなす
# messages.conf で定義済み
# 端末サイズ情報 ※携帯端末では必須, 形式は 幅x高さx密度
MSG_PHONE_IMG: str = "phone image size"
REQUIRED_PHONE_IMG: str = f"401,{MSG_PHONE_IMG} {MSG_REQUIRED}"
INVALID_PHONE_IMG: str = f"402,{MSG_PHONE_IMG} {MSG_INVALID}"
# リクエストパラメータ
PARAM_DEVICE: str = "device_name"
PARAM_START_DAY: str = "start_day"
PARAM_BOFORE_DAYS: str = "before_days"
PARAM_YEAR_MONTH: str = "year_month"
# リクエストパラメータエラー時のコード: 421番台以降
# デバイス名: 必須, 長さチェック (1-20byte), 未登録
DEVICE_LENGTH: int = 20
#  デバイスリスト取得クリエスと以外の全てのリクエスト
REQUIRED_DEVICE: str = f"421,{PARAM_DEVICE} {MSG_REQUIRED}"
INVALIDD_DEVICE: str = f"422,{PARAM_DEVICE} {MSG_INVALID}"
DEVICE_NOT_FOUND: str = f"423,{PARAM_DEVICE} {MSG_NOT_FOUND}"
# 期間指定画像取得リクエスト
#  (1)検索開始日["start_day"]: 任意 ※未指定ならシステム日付を検索開始日とする
#     日付形式(ISO8601: YYYY-mm-dd), 10文字一致
INVALID_START_DAY: str = f"431,{PARAM_START_DAY} {MSG_INVALID}"
#  (2)検索開始日から N日前 (1,2,3,7日): 必須
REQUIRED_BOFORE_DAY: str = f"433,{PARAM_BOFORE_DAYS} {MSG_REQUIRED}"
INVALID_BOFORE_DAY: str = f"434,{PARAM_BOFORE_DAYS} {MSG_INVALID}"
# 月間指定画像取得リクエスト
#   年月: 必須, 形式(YYYY-mm), 7文字一致
REQUIRED_YEAR_MONTH: str = f"435,{PARAM_YEAR_MONTH} {MSG_REQUIRED}"
INVALID_YEAR_MONTH: str = f"436,{PARAM_YEAR_MONTH} {MSG_INVALID}"

# エラーメッセージを格納する辞書オブジェクト定義
MSG_DESCRIPTION: str = "error_message"
# 固定メッセージエラー辞書オブジェクト
ABORT_DICT_UNMATCH_TOKEN: Dict[str, str] = {MSG_DESCRIPTION: app.config["UNMATCH_TOKEN"]}
# 可変メッセージエラー辞書オブジェクト: ""部分を置き換える
ABORT_DICT_BLANK_MESSAGE: Dict[str, str] = {MSG_DESCRIPTION: ""}


def get_connection() -> connection:
    if 'db' not in g:
        conn_pool: SimpleConnectionPool = app.config["postgreSQL_pool"]
        g.db: connection = conn_pool.getconn()
        g.db.set_session(readonly=True, autocommit=True)
        if app_logger_debug:
            app_logger.debug(f"g.db:{g.db}")
    return g.db


@app.teardown_appcontext
def close_connection(exception=None) -> None:
    db: connection = g.pop('db', None)
    if app_logger_debug:
        app_logger.debug(f"db:{db}")
    if db is not None:
        app.config["postgreSQL_pool"].putconn(db)


@app.route(APP_ROOT, methods=["GET"])
def index() -> str:
    """本日データ表示画面 (初回リクエストのみ)

    :return: 本日データ表示HTMLページ (matplotlibでプロットした画像含む)
    """
    if app_logger_debug:
        app_logger.debug(request.path)
    try:
        conn: connection = get_connection()
        # 年月日リスト取得
        dao = WeatherDao(conn, logger=app_logger)
        default_device_name: str = WEATHER_CONF["DEVICE_NAME"]
        yearMonthList: List[str] = dao.getGroupbyMonths(
            device_name=default_device_name,
            start_date=WEATHER_CONF["STA_YEARMONTH"],
        )
        # 本日データプロット画像取得
        # Browser用のリクエストでは開発機環境用にデバイス名を設定ファイルから取得する
        image_date_params = ImageDateParams(ImageDateType.TODAY)
        # ラズパイリリース版: 当日はシステム日付
        s_today = date.today().strftime('%Y-%m-%d')
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.TODAY] = s_today
        image_date_params.setParam(param)
        # データ件数, base64画像形式文字列
        rec_count: int
        img_base64_encoded: str
        rec_count, img_base64_encoded = gen_plot_image(
            conn, default_device_name, image_date_params, logger=app_logger
        )
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.codde, InternalServerError(original_exception=exp))

    # strToday: str = app.config.get("STR_TODAY", "")
    titleSuffix: str = app.config.get("TITLE_SUFFIX", "")
    defaultMainTitle: str = s_today + titleSuffix
    return render_template(
        "showplotweather.html",
        ip_host=app.config["SERVER_NAME"],
        app_root_url=APP_ROOT,
        path_get_today="/gettoday",
        path_get_month="/getmonth/",
        str_today=s_today,
        title_suffix=titleSuffix,
        info_today_update_interval=app.config.get("INFO_TODAY_UPDATE_INTERVAL"),
        default_main_title=defaultMainTitle,
        year_month_list=yearMonthList,
        img_src=img_base64_encoded,
    )


@app.route("/plot_weather/gettoday", methods=["GET"])
def getTodayImage() -> Response:
    """本日データ取得リクエスト(2回以降) JavaScriptからのリクエスト想定

    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:image/png;base64,... base64encoded data ...')
    """
    if app_logger_debug:
        app_logger.debug(request.path)
    try:
        conn: connection = get_connection()
        # 本日データプロット画像取得
        # ラズパイリリース版: 当日はシステム日付
        s_today = date.today().strftime('%Y-%m-%d')
        image_date_params = ImageDateParams(ImageDateType.TODAY)
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.TODAY] = s_today
        image_date_params.setParam(param)
        default_device_name: str = WEATHER_CONF["DEVICE_NAME"]
        # データ件数, base64画像形式文字列
        rec_count: int
        img_base64_encoded: str
        rec_count, img_base64_encoded = gen_plot_image(
            conn, default_device_name, image_date_params, logger=app_logger
        )
    except psycopg2.Error as db_err:
        app_logger.error(db_err)
        abort(InternalServerError.code, _set_errormessage(f"559,{db_err}"))
    except Exception as exp:
        app_logger.error(exp)
        return _createErrorImageResponse(InternalServerError.code)

    return _createImageResponse(img_base64_encoded)


@app.route("/plot_weather/getmonth/<yearmonth>", methods=["GET"])
def getMonthImage(yearmonth) -> Response:
    """要求された年月の月間データ取得

    :param yearmonth str: 年月 (例) 2022-01
    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:image/png;base64,... base64encoded data ...')
    """
    if app_logger_debug:
        app_logger.debug(request.path)
    try:
        # リクエストパラメータの妥当性チェック: "YYYY-mm" + "-01"
        chk_yyyymmdd = yearmonth + "-01"
        # 日付チェック(YYYY-mm-dd): 日付不正の場合例外スロー
        strdate2timestamp(chk_yyyymmdd, raise_error=True)
        conn: connection = get_connection()
        # Browser用のリクエストでは開発機環境用にデバイス名を設定ファイルから取得する
        default_device_name: str = WEATHER_CONF["DEVICE_NAME"]
        # 指定年月(year_month)データプロット画像取得
        image_date_params = ImageDateParams(ImageDateType.YEAR_MONTH)
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.YEAR_MONTH] = yearmonth
        image_date_params.setParam(param)
        # データ件数, base64画像形式文字列
        rec_count: int
        img_base64_encoded: str
        rec_count, img_base64_encoded = gen_plot_image(
            conn, default_device_name, image_date_params, logger=app_logger
        )
    except DateFormatError as dfe:
        # BAD Request
        app_logger.warning(dfe)
        return _createErrorImageResponse(BadRequest.code)
    except psycopg2.Error as db_err:
        # DBエラー
        app_logger.error(db_err)
        abort(InternalServerError.code, _set_errormessage(f"559,{db_err}"))
    except Exception as exp:
        # バグ, DBサーバーダウンなど想定
        app_logger.error(exp)
        return _createErrorImageResponse(InternalServerError.code)

    return _createImageResponse(img_base64_encoded)


@app.route("/plot_weather/getlastdataforphone", methods=["GET"])
def getLastDataForPhone() -> Response:
    """最新の気象データを取得する (スマートホン専用)
       [仕様変更] 2023-09-09
         (1) リクエストパラメータ追加
            device_name: デバイス名 ※必須
    
    :param: request parameter: device_name="xxxxx"
    """
    if app_logger_debug:
        app_logger.debug(request.path)
        # Debug output request.headers or request.arg or both
        _debugOutRequestObj(request, debugout=DebugOutRequest.HEADERS)

    # トークン必須
    headers: Headers = request.headers
    if not _matchToken(headers):
        abort(Forbidden.code, ABORT_DICT_UNMATCH_TOKEN)

    # デバイス名必須
    param_device_name: str = _checkDeviceName(request.args)
    try:
        conn: connection = get_connection()
        # 現在時刻時点の最新の気象データ取得
        dao = WeatherDao(conn, logger=app_logger)
        rec_count: int
        row: Optional[Tuple[str, float, float, float, float]]
        # デバイス名に対応する最新のレコード取得
        row = dao.getLastData(device_name=param_device_name)
        if row:
            rec_count = 1
            measurement_time, temp_out, temp_in, humid, pressure = row
            return _responseLastDataForPhone(
                measurement_time, temp_out, temp_in, humid, pressure, rec_count)
        else:
            # デバイス名に対応するレコード無し
            rec_count = 0
            return _responseLastDataForPhone(None, None, None, None, None, rec_count)
    except psycopg2.Error as db_err:
        app_logger.error(db_err)
        abort(InternalServerError.code, _set_errormessage(f"559,{db_err}"))
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))


@app.route("/plot_weather/getfirstregisterdayforphone", methods=["GET"])
def getFirstRegisterDayForPhone() -> Response:
    """デバイスの観測データの初回登録日を取得する (スマートホン専用)
       [仕様追加] 2023-09-13

           :param: request parameter: device_name="xxxxx"
    """
    if app_logger_debug:
        app_logger.debug(request.path)
        # Debug output request.headers or request.arg or both
        _debugOutRequestObj(request, debugout=DebugOutRequest.HEADERS)

    # トークン必須
    headers: Headers = request.headers
    if not _matchToken(headers):
        abort(Forbidden.code, ABORT_DICT_UNMATCH_TOKEN)

    # デバイス名必須
    param_device_name: str = _checkDeviceName(request.args)
    try:
        conn: connection = get_connection()
        dao = WeatherDao(conn, logger=app_logger)
        # デバイス名に対応する初回登録日取得
        first_register_day: Optional[str] = dao.getFisrtRegisterDay(param_device_name)
        if app_logger_debug:
            app_logger.debug(f"first_register_day[{type(first_register_day)}]: {first_register_day}")
        if first_register_day:
            return _responseFirstRegisterDayForPhone(first_register_day, 1)
        else:
            # デバイス名に対応するレコード無し
            return _responseFirstRegisterDayForPhone(None, 0)
    except psycopg2.Error as db_err:
        app_logger.error(db_err)
        abort(InternalServerError.code, _set_errormessage(f"559,{db_err}"))
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))


@app.route("/plot_weather/gettodayimageforphone", methods=["GET"])
def getTodayImageForPhone() -> Response:
    """本日データ画像取得リクエスト (スマートホン専用)
       [仕様変更] 2023-09-09
         (1) リクエストパラメータ追加
            device_name: デバイス名 ※必須
         (2) レスポンスにレコード件数を追加 ※0件エラーの抑止

    :param: request parameter: device_name="xxxxx"
    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:': 'img_src':'image/png;base64,... base64encoded data ...',
                         'rec_count':xxx)
    """
    if app_logger_debug:
        app_logger.debug(request.path)
        _debugOutRequestObj(request, debugout=DebugOutRequest.HEADERS)

    # トークン必須
    headers: Headers = request.headers
    if not _matchToken(headers):
        abort(Forbidden.code, ABORT_DICT_UNMATCH_TOKEN)

    # デバイス名必須
    param_device_name: str = _checkDeviceName(request.args)
    
    # 表示領域サイズ+密度は必須: 形式(横x縦x密度)
    str_img_size: str = _checkPhoneImageSize(headers)
    try:
        conn: connection = get_connection()
        # 当日はシステム日付
        s_today = date.today().strftime('%Y-%m-%d')
        image_date_params = ImageDateParams(ImageDateType.TODAY)
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.TODAY] = s_today
        param[ParamKey.PHONE_SIZE] = str_img_size
        image_date_params.setParam(param)
        rec_count: int
        img_base64_encoded: str
        rec_count, img_base64_encoded = gen_plot_image(
            conn, param_device_name, image_date_params, logger=app_logger
        )
        return _responseImageForPhone(rec_count, img_base64_encoded)
    except psycopg2.Error as db_err:
        app_logger.error(db_err)
        abort(InternalServerError.code, _set_errormessage(f"559,{db_err}"))
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))


@app.route("/plot_weather/getbeforedaysimageforphone", methods=["GET"])
def getBeforeDateImageForPhone() -> Response:
    """過去経過日指定データ画像取得リクエスト (スマートホン専用)
       [仕様変更] 2023-09-09
         (1) リクエストパラメータ追加
            device_name: デバイス名 ※必須
            start_day: 検索開始日(iso8601形式) ※任意
         (2) レスポンスにレコード件数を追加 ※0件エラーの抑止

    :param: request parameter: ?device_name=xxxxx&start_day=2023-05-01&before_days=(2|3|7)
    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:': 'img_src':'image/png;base64,... base64encoded data ...',
                         'rec_count':xxx)
    """
    if app_logger_debug:
        app_logger.debug(request.path)
        _debugOutRequestObj(request, debugout=DebugOutRequest.BOTH)

    # トークン必須
    headers = request.headers
    if not _matchToken(headers):
        abort(Forbidden.code, ABORT_DICT_UNMATCH_TOKEN)

    # デバイス名 ※必須チェック
    param_device_name: str = _checkDeviceName(request.args)
    # 検索開始日 ※任意、指定されている場合はISO8601形式チェック
    str_start_day: Optional[str] = _checkStartDay(request.args)
    if str_start_day is None:
        # 検索開始日がない場合は当日を設定
        str_start_day = date_util.getTodayIsoDate()
    # Check before_days query parameter
    str_before_days: str = _checkBeforeDays(request.args)

    # 表示領域サイズ+密度は必須: 形式(横x縦x密度)
    str_img_size: str = _checkPhoneImageSize(headers)
    try:
        conn: connection = get_connection()
        image_date_params = ImageDateParams(ImageDateType.RANGE)
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.START_DAY] = str_start_day
        param[ParamKey.BEFORE_DAYS] = str_before_days
        param[ParamKey.PHONE_SIZE] = str_img_size
        image_date_params.setParam(param)
        rec_count: int
        img_base64_encoded: str
        rec_count, img_base64_encoded = gen_plot_image(
            conn, param_device_name, image_date_params, logger=app_logger
        )
        return _responseImageForPhone(rec_count,img_base64_encoded)
    except psycopg2.Error as db_err:
        app_logger.error(db_err)
        abort(InternalServerError.code, _set_errormessage(f"559,{db_err}"))
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))


@app.route("/plot_weather/get_devices", methods=["GET"])
def getDevices() -> Response:
    """センサーディバイスリスト取得リクエスト

    :return: JSON形式(idを除くセンサーディバイスリスト)
         (出力内容) JSON({"data":{"devices":[...]}')
    """
    if app_logger_debug:
        app_logger.debug(request.path)

    devices_with_dict: List[Dict]
    try:
        conn: connection = get_connection()
        dao: DeviceDao = DeviceDao(conn, logger=app_logger)
        devices: List[DeviceRecord] = dao.get_devices()
        devices_with_dict = DeviceDao.to_dict_without_id(devices)
        resp_obj: Dict[str, Dict] = {
            "data": {"devices": devices_with_dict},
            "status": {"code": 0, "message": "OK"}
        }
        return _make_respose(resp_obj, 200)
    except psycopg2.Error as db_err:
        app_logger.error(db_err)
        abort(InternalServerError.code, _set_errormessage(f"559,{db_err}"))
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))


def _debugOutRequestObj(request, debugout=DebugOutRequest.ARGS) -> None:
    if debugout == DebugOutRequest.ARGS or debugout == DebugOutRequest.BOTH:
        app_logger.debug(f"reqeust.args: {request.args}")
    if debugout == DebugOutRequest.HEADERS or debugout == DebugOutRequest.BOTH:
        app_logger.debug(f"request.headers: {request.headers}")


def _matchToken(headers: Headers) -> bool:
    """トークン一致チェック
    :param headers: request header
    :return: if match token True, not False.
    """
    token_value: str = app.config.get("HEADER_REQUEST_PHONE_TOKEN_VALUE", "!")
    req_token_value: Optional[str] = headers.get(
        key=app.config.get("HEADER_REQUEST_PHONE_TOKEN_KEY", "!"),
        type=str,
        default=""
    )
    if req_token_value != token_value:
        app_logger.warning("Invalid request token!")
        return False
    return True


def _checkPhoneImageSize(headers: Headers) -> str:
    """
    ヘッダーに表示領域サイズ+密度([width]x[height]x[density])をつけてくる
    ※1.トークンチェックを通過しているのでセットされている前提で処理
    ※2.途中でエラー (Androidアプリ側のBUG) ならExceptionで補足されJSONでメッセージが返却される
    :param headers: request header
    :return: (imageWidth, imageHeight, density)
    """
    img_size: str = headers.get(
        app.config.get("HEADER_REQUEST_IMAGE_SIZE_KEY", ""), type=str, default=""
    )
    if app_logger_debug:
        app_logger.debug(f"Phone imgSize: {img_size}")
    if len(img_size) == 0:
        abort(BadRequest.code, _set_errormessage(REQUIRED_PHONE_IMG))

    sizes: List[str] = img_size.split("x")
    try:
        img_wd: int = int(sizes[0])
        img_ht: int = int(sizes[1])
        density: float = float(sizes[2])
        if app_logger_debug:
            app_logger.debug(f"imgWd: {img_wd}, imgHt: {img_ht}, density: {density}")
        return img_size
    except Exception as exp:
        # ログには例外メッセージ
        app_logger.warning(f"[phone image size] {exp}")
        abort(BadRequest.code, _set_errormessage(INVALID_PHONE_IMG))


def _checkBeforeDays(args: MultiDict) -> str:
    # QueryParameter: before_days in (1,2,3,7)
    # before_days = args.get("before_days", default=-1, type=int)
    # args.get(key): keyが無い場合も キーが有る場合で数値以外でも -1 となり必須チェックができない
    # before_days = args.pop("before_days"): TypeError: 'ImmutableMultiDict' objects are immutable
    if len(args.keys()) == 0 or PARAM_BOFORE_DAYS not in args.keys():
        abort(BadRequest.code, _set_errormessage(REQUIRED_BOFORE_DAY))

    before_days = args.get(PARAM_BOFORE_DAYS, default=-1, type=int)
    if before_days not in [1,2,3,7]:
        abort(BadRequest.code, _set_errormessage(INVALID_BOFORE_DAY))

    return  str(before_days)


def _checkDeviceName(args: MultiDict) -> str:
    """デバイス名チェック
        パラメータなし: abort(BadRequest)
        該当レコードなし: abort(NotFound)
    return デバイス名    
    """
    # 必須チェック
    if len(args.keys()) == 0 or PARAM_DEVICE not in args.keys():
        abort(BadRequest.code, _set_errormessage(REQUIRED_DEVICE))

    # 長さチェック: 1 - 20
    param_device_name: str = args.get(PARAM_DEVICE, default="", type=str)
    chk_size: int = len(param_device_name)
    if chk_size < 1 or chk_size > DEVICE_LENGTH:    
        abort(BadRequest.code, _set_errormessage(INVALIDD_DEVICE))

    # 存在チェック
    if app_logger_debug:
        app_logger.debug("requestParam.device_name: " + param_device_name)

    exists: bool = False
    try:
        conn: connection = get_connection()
        dao: DeviceDao = DeviceDao(conn, logger=app_logger)
        exists = dao.exists(param_device_name)
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))

    if exists is True:
        return param_device_name
    else:
        abort(BadRequest.code, _set_errormessage(DEVICE_NOT_FOUND))


def _checkStartDay(args: MultiDict) -> Optional[str]:
    """検索開始日の形式チェック
        パラメータなし: OK
        パラメータ有り: ISO8601形式チェック
    return 検索開始日 | None    
    """
    if len(args.keys()) == 0 or PARAM_START_DAY not in args.keys():
        return None

    # 形式チェック
    param_start_day: str = args.get(PARAM_START_DAY, default="", type=str)
    if app_logger_debug:
        app_logger.debug(f"start_day: {param_start_day}")
    valid: bool = date_util.checkIso8601Date(param_start_day)
    if valid is True:
        return param_start_day
    else:
        # 不正パラメータ
        abort(BadRequest.code, _set_errormessage(INVALID_START_DAY))


def _createImageResponse(img_src: str) -> Response:
    """画像レスポンスを返却する (JavaScript用)"""
    resp_obj = {"status": "success", "data": {"img_src": img_src}}
    return _make_respose(resp_obj, 200)


def _createErrorImageResponse(err_code) -> Response:
    """エラー画像レスポンスを返却する (JavaScript用)"""
    resp_obj = {"status": "error", "code": err_code}
    if err_code == BadRequest.code:
        resp_obj["data"] = {"img_src": BAD_REQUEST_IMAGE_DATA}
    elif err_code == InternalServerError.code:
        resp_obj["data"] = {"img_src": INTERNAL_SERVER_ERROR_IMAGE_DATA}
    return _make_respose(resp_obj, err_code)


def _responseLastDataForPhone(
        mesurement_time: str,
        temp_out: float,
        temp_in: float,
        humid: float,
        pressure: float,
        rec_count: int
        ) -> Response:
    """気象データの最終レコードを返却する (スマホアプリ用)"""
    resp_obj: Dict[str, Dict[str, Union[str, float]]] = {
        "status":
            {"code": 0, "message": "OK"},
        "data": {
            "measurement_time": mesurement_time,
            "temp_out": temp_out,
            "temp_in": temp_in,
            "humid": humid,
            "pressure": pressure,
            "rec_count": rec_count
        }
    }
    return _make_respose(resp_obj, 200)


def _responseFirstRegisterDayForPhone(
        first_day: Optional[str],
        rec_count: int
        ) -> Response:
    """気象データの初回登録日を返却する (スマホアプリ用)"""
    resp_obj: Dict[str, Dict[str, Union[str, int]]] = {
        "status":
            {"code": 0, "message": "OK"},
        "data": {
            "first_register_day": first_day,
            "rec_count": rec_count
        }
    }
    return _make_respose(resp_obj, 200)


def _responseImageForPhone(rec_count: int, img_src: str) -> Response:
    """Matplotlib生成画像を返却する (スマホアプリ用)
       [仕様変更] 2023-09-09
         レスポンスにレコード件数を追加 ※0件エラーの抑止
    """
    resp_obj: Dict[str, Dict[str, Union[int, str]]] = {
        "status": {"code": 0, "message": "OK"},
        "data": {
            "img_src": img_src, 
            "rec_count": rec_count
         }
    }
    return _make_respose(resp_obj, 200)


def _set_errormessage(message: str) -> Dict:
    ABORT_DICT_BLANK_MESSAGE[MSG_DESCRIPTION] = message
    return ABORT_DICT_BLANK_MESSAGE


# Request parameter check error.
@app.errorhandler(BadRequest.code)
# Token error.
@app.errorhandler(Forbidden.code)
# Device not found.
@app.errorhandler(NotFound.code)
@app.errorhandler(InternalServerError.code)
def error_handler(error: HTTPException) -> Response:
    app_logger.warning(f"error_type:{type(error)}, {error}")
    # Bugfix: 2023-09-06
    err_msg: str
    if isinstance(error.description, dict):
        # アプリが呼び出すabort()の場合は辞書オブジェクト
        err_msg = error.description["error_message"]
    else:
        # Flaskが出す場合は HTTPException)
        err_msg = error.description
    resp_obj: Dict[str, Dict[str, Union[int, str]]] = {
        "status": {"code": error.code, "message": err_msg}
    }
    return _make_respose(resp_obj, error.code)


def _make_respose(resp_obj: Dict, resp_code) -> Response:
    response = make_response(jsonify(resp_obj), resp_code)
    response.headers["Content-Type"] = "application/json"
    return response
