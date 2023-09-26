import os

from ..util import file_util as FU

_base_dir = os.path.abspath(os.path.dirname(__file__))
_conf_path = os.path.join(_base_dir, "conf")

PLOT_CONF = FU.read_json(os.path.join(_conf_path, "plot_weather.json"))
WEATHER_CONF = FU.read_json(os.path.join(_conf_path, "weather.json"))
