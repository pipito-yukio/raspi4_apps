from typing import Dict, List, Optional, Union

from flask import (
    abort, g, jsonify, render_template, request, make_response,Response
)
from werkzeug.exceptions import HTTPException
from plot_weather import (BAD_REQUEST_IMAGE_DATA,
                          INTERNAL_SERVER_ERROR_IMAGE_DATA, DebugOutRequest,
                          app, app_logger, app_logger_debug)
from plot_weather.dao.weathercommon import WEATHER_CONF
from plot_weather.dao.weatherdao import WeatherDao
from plot_weather.db.sqlite3conv import DateFormatError, strdate2timestamp
from plot_weather.plotter.plotterweather import (
    ImageDateType, gen_plot_image, ImageDateParams, ParamKey
)
from werkzeug.exceptions import BadRequest, Forbidden, InternalServerError
from werkzeug.datastructures import Headers, MultiDict
from psycopg2.pool import SimpleConnectionPool
from psycopg2._psycopg import connection

APP_ROOT: str = app.config["APPLICATION_ROOT"]
MSG_TITLE_SUFFIX:str = app.config["TITLE_SUFFIX"]
MSG_STR_TODAY: str = app.config["STR_TODAY"]
ABORT_DICT_UNMATCH_TOKEN: Dict[str, str] = {"error_message": app.config["UNMATCH_TOKEN"]}
ABORT_DICT_REQURE_PHONE_IMGSIZE: Dict[str, str] = {
    "error_message": app.config["REQUIRE_PHONE_IMG_SIZE"]
}
ABORT_DICT_BLANK_MESSAGE: Dict[str, str] = {"error_message": ""}


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
        yearMonthList: List[str] = dao.getGroupbyMonths(
            device_name=WEATHER_CONF["DEVICE_NAME"],
            start_date=WEATHER_CONF["STA_YEARMONTH"],
        )
        if app_logger_debug:
            app_logger.debug(f"yearMonthList:{yearMonthList}")
        # 本日データプロット画像取得
        image_date_params = ImageDateParams(ImageDateType.TODAY)
        imgBase64Encoded: str = gen_plot_image(
            conn, image_date_params=image_date_params, logger=app_logger
        )
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.codde, InternalServerError(original_exception=exp))

    strToday: str = app.config.get("STR_TODAY", "")
    titleSuffix: str = app.config.get("TITLE_SUFFIX", "")
    defaultMainTitle: str = strToday + titleSuffix
    return render_template(
        "showplotweather.html",
        ip_host=app.config["SERVER_NAME"],
        app_root_url=APP_ROOT,
        path_get_today="/gettoday",
        path_get_month="/getmonth/",
        str_today=strToday,
        title_suffix=titleSuffix,
        info_today_update_interval=app.config.get("INFO_TODAY_UPDATE_INTERVAL"),
        default_main_title=defaultMainTitle,
        year_month_list=yearMonthList,
        img_src=imgBase64Encoded,
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
        image_date_params = ImageDateParams(ImageDateType.TODAY)
        imgBase64Encoded: str = gen_plot_image(
            conn, image_date_params, logger=app_logger
        )
    except Exception as exp:
        app_logger.error(exp)
        return _createErrorImageResponse(InternalServerError.code)

    return _createImageResponse(imgBase64Encoded)


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
        # 指定年月(year_month)データプロット画像取得
        image_date_params = ImageDateParams(ImageDateType.YEAR_MONTH)
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.YEAR_MONTH] = yearmonth
        image_date_params.setParam(param)
        imgBase64Encoded:str = gen_plot_image(
            conn, image_date_params, logger=app_logger
        )
    except DateFormatError as dfe:
        # BAD Request
        app_logger.warning(dfe)
        return _createErrorImageResponse(BadRequest.code)
    except Exception as exp:
        # ここにくるのはDBエラー・バグなど想定
        app_logger.error(exp)
        return _createErrorImageResponse(InternalServerError.code)

    return _createImageResponse(imgBase64Encoded)


@app.route("/plot_weather/getlastdataforphone", methods=["GET"])
def getLastDataForPhone() -> Response:
    """最新の気象データを取得する (スマートホン専用)"""
    if app_logger_debug:
        app_logger.debug(request.path)
        # Debug output request.headers or request.arg or both
        _debugOutRequestObj(request, debugout=DebugOutRequest.HEADERS)

    # トークン必須
    headers: Headers = request.headers
    if not _matchToken(headers):
        abort(Forbidden.code, ABORT_DICT_UNMATCH_TOKEN)

    try:
        conn: connection = get_connection()
        # 現在時刻時点の最新の気象データ取得
        dao = WeatherDao(conn, logger=app_logger)
        (measurement_time, temp_out, temp_in, humid, pressure) = dao.getLastData(
            device_name=WEATHER_CONF["DEVICE_NAME"]
        )
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))

    return _responseLastDataForPhone(measurement_time, temp_out, temp_in, humid, pressure)


@app.route("/plot_weather/gettodayimageforphone", methods=["GET"])
def getTodayImageForPhone() -> Response:
    """本日データ画像取得リクエスト (スマートホン専用)

    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:image/png;base64,... base64encoded data ...')
    """
    if app_logger_debug:
        app_logger.debug(request.path)
        _debugOutRequestObj(request, debugout=DebugOutRequest.HEADERS)

    # トークン必須
    headers: Headers = request.headers
    if not _matchToken(headers):
        abort(Forbidden.code, ABORT_DICT_UNMATCH_TOKEN)

    # 表示領域サイズ+密度は必須: 形式(横x縦x密度)
    str_img_size: str = _checkPhoneImageSize(headers)
    try:
        conn: connection = get_connection()
        image_date_params = ImageDateParams(ImageDateType.TODAY)
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.PHONE_SIZE] = str_img_size
        image_date_params.setParam(param)
        imgBase64Encoded:str = gen_plot_image(
            conn, image_date_params, logger=app_logger
        )
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))

    return _responseImageForPhone(imgBase64Encoded)


@app.route("/plot_weather/getbeforedaysimageforphone", methods=["GET"])
def getBeforeDateImageForPhone() -> Response:
    """過去経過日指定データ画像取得リクエスト (スマートホン専用)

    :param: request parameter: ?before_days=(2|3|7)
    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:image/png;base64,... base64encoded data ...')
    """
    if app_logger_debug:
        app_logger.debug(request.path)
        _debugOutRequestObj(request, debugout=DebugOutRequest.BOTH)

    # トークン必須
    headers = request.headers
    if not _matchToken(headers):
        abort(Forbidden.code, ABORT_DICT_UNMATCH_TOKEN)

    # Check before_days query parameter
    str_before_days: str = _checkBeforeDays(request.args)

    # 表示領域サイズ+密度は必須: 形式(横x縦x密度)
    str_img_size: str = _checkPhoneImageSize(headers)
    try:
        conn: connection = get_connection()
        image_date_params = ImageDateParams(ImageDateType.RANGE)
        param: Dict[ParamKey, str] = image_date_params.getParam()
        param[ParamKey.BEFORE_DAYS] = str_before_days
        param[ParamKey.PHONE_SIZE] = str_img_size
        image_date_params.setParam(param)
        imgBase64Encoded:str = gen_plot_image(
            conn, image_date_params, logger=app_logger
        )
    except Exception as exp:
        app_logger.error(exp)
        abort(InternalServerError.code, description=str(exp))

    return _responseImageForPhone(imgBase64Encoded)


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
        abort(BadRequest.code, ABORT_DICT_REQURE_PHONE_IMGSIZE)

    sizes: List[str] = img_size.split("x")
    try:
        img_wd: int = int(sizes[0])
        img_ht: int = int(sizes[1])
        density: float = float(sizes[2])
    except Exception as exp:
        # ログには例外メッセージ
        app_logger.warning(f"[phone image size] {exp}")
        # アボートレスポンスは不正パラメータ
        ABORT_DICT_BLANK_MESSAGE["error_message"] = app.config["INVALID_BEFORE_DAYS"]
        abort(BadRequest.code, ABORT_DICT_BLANK_MESSAGE)
    if app_logger_debug:
        app_logger.debug(f"imgWd: {img_wd}, imgHt: {img_ht}, density: {density}")

    return img_size


def _checkBeforeDays(args: MultiDict) -> str:
    # QueryParameter: before_days in (1,2,3,7)
    # before_days = args.get("before_days", default=-1, type=int)
    # args.get(key): keyが無い場合も キーが有る場合で数値以外でも -1 となり必須チェックができない
    # before_days = args.pop("before_days"): TypeError: 'ImmutableMultiDict' objects are immutable
    if len(args.keys()) == 0 or "before_days" not in args.keys():
        ABORT_DICT_BLANK_MESSAGE["error_message"] = app.config["REQUIRE_BEFORE_DAYS"]
        abort(BadRequest.code, ABORT_DICT_BLANK_MESSAGE)

    before_days = args.get("before_days", default=-1, type=int)
    if before_days not in [1,2,3,7]:
        ABORT_DICT_BLANK_MESSAGE["error_message"] = app.config["INVALID_BEFORE_DAYS"]
        abort(BadRequest.code, ABORT_DICT_BLANK_MESSAGE)

    return  str(before_days)


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
        pressure: float) -> Response:
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
        }
    }
    return _make_respose(resp_obj, 200)


def _responseImageForPhone(img_src: str) -> Response:
    """Matplotlib生成画像を返却する (スマホアプリ用)"""
    resp_obj: Dict[str, Dict[str, Union[int, str]]] = {
        "status": {"code": 0, "message": "OK"}, "data": {"img_src": img_src}
    }
    return _make_respose(resp_obj, 200)


@app.errorhandler(400)
@app.errorhandler(403)
def error_handler(error: HTTPException) -> Response:
    app_logger.warning(f"error_type:{type(error)}, {error}")
    resp_obj: Dict[str, Dict[str, Union[int, str]]] = {
        "status": {"code": error.code, "message": error.description["error_message"]}
    }
    return _make_respose(resp_obj, error.code)


@app.errorhandler(InternalServerError.code)
def internal_server_error(error: InternalServerError) -> Response:
    app_logger.warning(f"error_type:{type(error)}, error_description: {error.description}")
    # InternalExceptionはerror.descriptionはOK、error.description["error_message"] 例外発生
    resp_obj: Dict[str, Dict[str, Union[int, str]]] = {
        "status": {"code": error.code, "message": error.description}
    }
    return _make_respose(resp_obj, InternalServerError.code)


def _make_respose(resp_obj: Dict, resp_code) -> Response:
    response = make_response(jsonify(resp_obj), resp_code)
    response.headers["Content-Type"] = "application/json"
    return response
