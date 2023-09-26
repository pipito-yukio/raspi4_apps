import os
from pathlib import Path
from datetime import datetime
import logging
import logging.config
import json

# Development environment (On Ubuntu): .bash_rc in "PATH_LOGGER_CONF", "PATH_APP_LOGS"
# default: RaspberryPi environment
# log config file path
my_home = os.environ.get("HOME", "/home/pi")
path_log_conf = os.environ.get("PATH_LOGGER_CONF", os.path.join(my_home, "bin/pigpio/conf"))
# output logfile directory
path_app_logs = os.environ.get("PATH_APP_LOGS=", os.path.join(my_home, "logs/pigpio"))

__instance = None


def create_logger(app_name):
    print("create_logger(app_name:{})".format(app_name))
    global __instance
    if __instance is None:
        _init("logconf_{}.json".format(app_name))
        __instance = object()
    return logging.getLogger(app_name)


def get_logger(name):
    print("get_logger({})".format(name))
    return logging.getLogger(name)


def _init(logconf_name):
    logconf_file = os.path.join(path_log_conf, logconf_name)
    with open(logconf_file) as fp:
        logconf = json.load(fp)
    fmt_filename = logconf['handlers']['fileHandler']['filename']
    # "filename": "{}/xxxxxxx.log"
    filename = fmt_filename.format(path_app_logs)
    fullpath = os.path.expanduser(filename)
    logdir = Path(os.path.dirname(fullpath))
    if not logdir.exists():
        logdir.mkdir(parents=True)

    base, extension = os.path.splitext(fullpath)
    datepart = datetime.now().strftime("%Y%m%d%H%M")
    filename = "{}_{}{}".format(base, datepart, extension)
    print("logFile:{}".format(filename))
    # Override
    logconf['handlers']['fileHandler']['filename'] = filename
    logging.config.dictConfig(logconf)
