from flask import abort, g, jsonify, render_template, request
from plot_weather import (BAD_REQUEST_IMAGE_DATA,
                          INTERNAL_SERVER_ERROR_IMAGE_DATA, app, app_logger)
from plot_weather.dao.weathercommon import WEATHER_CONF
from plot_weather.dao.weatherdao import WeatherDao
from plot_weather.db.sqlite3conv import DateFormatError, strdate2timestamp
from plot_weather.plotter.plotterweather import gen_plotimage
from werkzeug.exceptions import BadRequest

APP_ROOT = app.config["APPLICATION_ROOT"]
CODE_BAD_REQUEST, CODE_FORBIDDEN, CODE_INTERNAL_SERVER_ERROR = 400, 403, 500
MSG_TITLE_SUFFIX = app.config["TITLE_SUFFIX"]
MSG_STR_TODAY = app.config["STR_TODAY"]


def get_dbconn():
    if 'db' not in g:
        g.db = app.config["postgreSQL_pool"].getconn()
        g.db.set_session(readonly=True, autocommit=True)
        app_logger.debug(f"g.db:{g.db}")
    return g.db


@app.teardown_appcontext
def close_conn(exception=None):
    db = g.pop('db', None)
    app_logger.debug(f"db:{db}")
    if db is not None:
        app.config["postgreSQL_pool"].putconn(db)


@app.errorhandler(BadRequest)
def incorrect_access(ex):
    return "Bad request !", CODE_BAD_REQUEST


@app.route(APP_ROOT, methods=["GET"])
def index():
    """本日データ表示画面 (初回リクエストのみ)

    :return: 本日データ表示HTMLページ (matplotlibでプロットした画像含む)
    """
    try:
        conn = get_dbconn()
        # 年月日リスト取得
        dao = WeatherDao(conn, logger=app_logger)
        yearMonthList = dao.getGroupbyMonths(
            device_name=WEATHER_CONF["DEVICE_NAME"],
            start_date=WEATHER_CONF["STA_YEARMONTH"],
        )
        app_logger.debug(f"yearMonthList:{yearMonthList}")
        # 本日データプロット画像取得
        imgBase64Encoded = gen_plotimage(conn, logger=app_logger)
    except Exception as exp:
        app_logger.error(exp)
        return abort(CODE_INTERNAL_SERVER_ERROR)

    strToday = app.config.get("STR_TODAY")
    titleSuffix = app.config.get("TITLE_SUFFIX")
    defaultMainTitle = strToday + titleSuffix
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
def getTodayImage():
    """本日データ取得リクエスト(2回以降) JavaScriptからのリクエスト想定

    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:image/png;base64,... base64encoded data ...')
    """
    app_logger.debug("getTodayImage()")
    try:
        conn = get_dbconn()
        # 本日データプロット画像取得
        imgBase64Encoded = gen_plotimage(conn, year_month=None, logger=app_logger)
    except Exception as exp:
        app_logger.error(exp)
        return _create_image_error_response(CODE_INTERNAL_SERVER_ERROR)

    return _create_image_response(imgBase64Encoded)


@app.route("/plot_weather/getmonth/<yearmonth>", methods=["GET"])
def getMonthImage(yearmonth):
    """要求された年月の月間データ取得

    :param yearmonth str: 年月 (例) 2022-01
    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:image/png;base64,... base64encoded data ...')
    """
    app_logger.debug(f"yearmonth: {yearmonth}")
    try:
        # リクエストパラメータの妥当性チェック: "YYYY-mm" + "-01"
        chk_yyyymmdd = yearmonth + "-01"
        # 日付チェック(YYYY-mm-dd): 日付不正の場合例外スロー
        strdate2timestamp(chk_yyyymmdd, raise_error=True)
        conn = get_dbconn()
        # 指定年月(year_month)データプロット画像取得
        imgBase64Encoded = gen_plotimage(conn, year_month=yearmonth, logger=app_logger)
    except DateFormatError as dfe:
        # BAD Request
        app_logger.warning(dfe)
        return _create_image_error_response(CODE_BAD_REQUEST)
    except Exception as exp:
        # ここにくるのはDBエラー・バグなど想定
        app_logger.error(exp)
        return _create_image_error_response(CODE_INTERNAL_SERVER_ERROR)

    return _create_image_response(imgBase64Encoded)


@app.route("/plot_weather/getlastdataforphone", methods=["GET"])
def getLastDataForPhone():
    """最新の気象データを取得する (スマートホン専用)"""
    app_logger.debug("getlastdataforphone()")
    headers = request.headers
    app_logger.debug(f"headers: {headers}")
    # トークン必須
    token_value = app.config.get("HEADER_REQUEST_PHONE_TOKEN_VALUE")
    req_token_value = headers.get(app.config.get("HEADER_REQUEST_PHONE_TOKEN_KEY"))
    if req_token_value != token_value:
        # トークンが一致しなければエラー画面を返却 ※アプリからは同じトークンがセットされている
        app_logger.warning("Invalid request token!")
        return abort(CODE_FORBIDDEN)

    try:
        conn = get_dbconn()
        # 現在時刻時点の最新の気象データ取得
        dao = WeatherDao(conn, logger=app_logger)
        (measurement_time, temp_out, temp_in, humid, pressure) = dao.getLastData(
            device_name=WEATHER_CONF["DEVICE_NAME"]
        )
    except Exception as exp:
        app_logger.error(exp)
        abort(CODE_INTERNAL_SERVER_ERROR, description=str(exp))

    return _response_lastdataforphone(
        measurement_time, temp_out, temp_in, humid, pressure
    )


@app.route("/plot_weather/gettodayimageforphone", methods=["GET"])
def getTodayImageForPhone():
    """本日データ取得リクエスト (スマートホン専用)

    :return: jSON形式(matplotlibでプロットした画像データ(形式: png)のbase64エンコード済み文字列)
         (出力内容) jSON('data:image/png;base64,... base64encoded data ...')
    """
    app_logger.debug("getTodayImageForPhone()")
    headers = request.headers
    app_logger.debug(f"headers: {headers}")
    # トークン必須
    token_value = app.config.get("HEADER_REQUEST_PHONE_TOKEN_VALUE")
    req_token_value = headers.get(app.config.get("HEADER_REQUEST_PHONE_TOKEN_KEY"))
    if req_token_value != token_value:
        app_logger.warning("Invalid request token!")
        return abort(CODE_FORBIDDEN)

    try:
        # ヘッダーに表示領域サイズ+密度([width]x[height]x[density])をつけてくる
        # ※1.トークンチェックを通過しているのでセットされている前提で処理
        # ※2.途中でエラー (Androidアプリ側のBUG) ならExceptionで補足されJSONでメッセージが返却される
        img_size = headers.get(app.config.get("HEADER_REQUEST_IMAGE_SIZE_KEY"))
        app_logger.debug(f"Phone imgSize: {img_size}")
        img_wd, img_ht, density = 0, 0, 1.0
        if img_size is not None:
            sizes = img_size.split("x")
            img_wd = int(sizes[0])
            img_ht = int(sizes[1])
            density = float(sizes[2])
        app_logger.debug(f"imgWd: {img_wd}, imgHt: {img_ht}, density: {density}")

        conn = get_dbconn()
        imgBase64Encoded = gen_plotimage(
            conn,
            width_pixel=(None if img_wd == 0 else img_wd),
            height_pixel=(None if img_ht == 0 else img_ht),
            density=(density if density > 0 else None),
            year_month=None,
            logger=app_logger,
        )
    except Exception as exp:
        app_logger.error(exp)
        abort(CODE_INTERNAL_SERVER_ERROR, description=str(exp))

    return _response_todayimageforphone(imgBase64Encoded)


def _create_image_response(img_src):
    """画像レスポンスを返却する (JavaScript用)"""
    resp_obj = {"status": "success"}
    resp_obj["data"] = {"img_src": img_src}
    return jsonify(resp_obj)


def _create_image_error_response(err_code):
    """エラー画像レスポンスを返却する (JavaScript用)"""
    resp_obj = {"status": "error", "code": err_code}
    if err_code == CODE_BAD_REQUEST:
        resp_obj["data"] = {"img_src": BAD_REQUEST_IMAGE_DATA}
    else:
        resp_obj["data"] = {"img_src": INTERNAL_SERVER_ERROR_IMAGE_DATA}
    response = jsonify(resp_obj)
    # レスポンスコードを指定されたエラーコードで上書きする
    response.status_code = err_code
    return response


def _response_lastdataforphone(mesurement_time, temp_out, temp_in, humid, pressure):
    """気象データの最終レコードを返却する (スマホアプリ用)"""
    resp_obj = {}
    resp_obj["status"] = {"code": 0, "message": "OK"}
    resp_obj["data"] = {
        "measurement_time": mesurement_time,
        "temp_out": temp_out,
        "temp_in": temp_in,
        "humid": humid,
        "pressure": pressure,
    }
    return jsonify(resp_obj)


def _response_todayimageforphone(img_src):
    """本日データの気象データ画像を返却する (スマホアプリ用)"""
    resp_obj = {}
    resp_obj["status"] = {"code": 0, "message": "OK"}
    resp_obj["data"] = {"img_src": img_src}
    return jsonify(resp_obj)


def _error_response_forphone(error):
    """テキストのエラーレスポンスを返却するする (スマホアプリ用)"""
    resp_obj = {}
    resp_obj["status"] = {"code": error.code, "message": error.description}
    return jsonify(resp_obj)


@app.errorhandler(CODE_BAD_REQUEST)
@app.errorhandler(CODE_INTERNAL_SERVER_ERROR)
def error_handler(error):
    return _error_response_forphone(error), error.code
