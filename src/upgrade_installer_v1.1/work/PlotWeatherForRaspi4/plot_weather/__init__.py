import enum
import logging
import os
import socket
import uuid
from typing import Dict

from psycopg2.pool import SimpleConnectionPool
from flask import Flask

from plot_weather.log import logsetting
from plot_weather.util.file_util import read_json
from plot_weather.util.image_util import image_to_base64encoded


class DebugOutRequest(enum.Enum):
    ARGS = 0
    HEADERS = 1
    BOTH = 2


# PostgreSQL connection information json file.
CONF_PATH: str = os.path.expanduser("~/bin/pigpio/conf")
DB_CONF_PATH: str = os.path.join(CONF_PATH, "dbconf.json")
DB_CONN_MAX: int = int(os.environ.get("DB_CONN_MAX", "5"))

app = Flask(__name__, static_url_path='/static')
# ロガーを本アプリ用のものに設定する
app_logger: logging.Logger = logsetting.get_logger("app_main")
app_logger_debug: bool = (app_logger.getEffectiveLevel() <= logging.DEBUG)
app.config.from_object("plot_weather.config")
# HTMLテンプレートに使うメッセージキーをapp.configに読み込み
app.config.from_pyfile(os.path.join(".", "messages/messages.conf"), silent=False)
# リクエストヘッダに設定するキーをapp.configに読み込み
app.config.from_pyfile(os.path.join(".", "messages/requestkeys.conf"), silent=False)
# セッション用の秘密キー
app.secret_key = uuid.uuid4().bytes
# Strip newline
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True

# サーバホストとセッションのドメインが一致しないとブラウザにセッションIDが設定されない
IP_HOST: str = os.environ.get("IP_HOST", "localhost")
FLASK_PROD_PORT: str = os.environ.get("FLASK_PROD_PORT", "8080")
has_prod: bool = os.environ.get("FLASK_ENV", "development") == "production"
SERVER_HOST: str
if has_prod:
    # Production mode
    SERVER_HOST = IP_HOST + ":" + FLASK_PROD_PORT
else:
    SERVER_HOST = IP_HOST + ":5000"
app_logger.info("SERVER_HOST: {}".format(SERVER_HOST))

app.config["SERVER_NAME"] = SERVER_HOST
app.config["APPLICATION_ROOT"] = "/plot_weather"
# use flask jsonify with japanese message
app.config["JSON_AS_ASCII"] = False
if app_logger_debug:
    app_logger.debug(f"{app.config}")
# "BAD REQUEST"用画像のbase64エンコード文字列ファイル
curr_dir: str = os.path.dirname(__file__)
cotent_path: str = os.path.join(curr_dir, "static", "content")
file_bad_request: str = os.path.join(cotent_path, "BadRequest_png_base64encoded.txt")
BAD_REQUEST_IMAGE_DATA: str = image_to_base64encoded(file_bad_request)
# "Internal Server Error"用画像のbase64エンコード文字列ファイル
file_internal_error: str = os.path.join(
    cotent_path, "InternalServerError_png_base64encoded.txt"
)
INTERNAL_SERVER_ERROR_IMAGE_DATA: str = image_to_base64encoded(file_internal_error)
# Database connection pool
dbconf: Dict[str, str] = read_json(DB_CONF_PATH)
dbconf["host"] = dbconf["host"].format(hostname=socket.gethostname())
if app_logger_debug:
    app_logger.debug(f"dbconf: {dbconf}")
conn_pool = SimpleConnectionPool(1, DB_CONN_MAX, **dbconf)
app_logger.info(f"postgreSQL_pool(max={DB_CONN_MAX}): {conn_pool}")
app.config["postgreSQL_pool"] = conn_pool

# Application main program
from plot_weather.views import app_main
