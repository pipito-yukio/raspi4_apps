from psycopg2 import DatabaseError
from .sqlite3conv import to_float

"""
Weather database CRUD functions, Finder class 
"""

# Weather database file path: (*)Environment on system service

# PostgreSQL: schema~weather
INSERT_DEVICE = "INSERT INTO weather.t_device(name) VALUES (%(name)s) RETURNING id"
ALL_DEVICES = "SELECT id, name FROM weather.t_device ORDER BY id"
FIND_DEVICE = "SELECT id FROM weather.t_device WHERE name=%(name)s"

INSERT_WEATHER = """
INSERT INTO weather.t_weather(did, measurement_time, temp_out, temp_in, humid, pressure) VALUES (
 %(did)s,
 %(measurement_time)s,
 %(temp_out)s,
 %(temp_in)s,
 %(humid)s,
 %(pressure)s
 )
"""
TRUNCATE_WEATHER = """
TRUNCATE TABLE weather.t_weather;
"""

# Global flag
flag_truncating = False
# t_device cache: {name: id}
_cache_did_map = {}


def load_device_cache(conn, logger):
    _cache_did_map = all_devices(conn, logger)
    if logger is not None:
        logger.debug(_cache_did_map)


def get_did(conn, device_name, add_device=True, logger=None):
    """
    Get the device ID corresponding to the device name.
    1. if exist in cache, return from cache.
    2. if not exist in cache, if exist in t_device return did
    3. if not exist in t_device, insert into t_device and return did
    :param conn: Weather Weather database connection
    :param device_name: Device name
    :param add_device: flag into t_device, if True then insert into t_device and cache
    :param logger: application logger or None
    :return: did
    """
    try:
        did = _cache_did_map[device_name]
    except KeyError:
        did = None

    if did is not None:
        return did

    did = find_device(conn, device_name, logger)
    if did is not None:
        _cache_did_map[device_name] = did
        return did

    if not add_device:
        return None

    did = add_device(conn, device_name, logger)
    _cache_did_map[device_name] = did
    return did


def all_devices(conn, logger=None):
    """
    All record name-ID dict in t_device
    :param logger: application logger or None
    :return: Dict {device name: id}, if not record then blank dict
    """
    devices = {}
    with conn.cursor() as cursor:
        cursor.execute(ALL_DEVICES)
        if logger is not None:
            logger.debug(f"rowcount: {cursor.rowcount}")
        for device in cursor.fetchall():
            devices[device[1]] = device[0] # {key: name, value: id}
    return devices


def find_device(conn, device_name, logger=None):
    """
    Check device name in t_device.
    :param conn: Weather database connection
    :param device_name: Device name
    :param logger: application logger or None
    :return: if exists then Device ID else None
    """
    with conn.cursor() as cursor:
        cursor.execute(FIND_DEVICE, {'name': device_name,})
        rec = cursor.fetchone()
    if logger is not None:
        logger.debug("{}: {}".format(device_name, rec))
    if rec is not None:
        rec = rec[0]
    return rec


def add_device(conn, device_name, logger=None):
    """
    Insert Device name to t_device and return inserted ID.
    :param conn: Weather database connection
    :param device_name: Device name
    :param logger: application logger or None
    :return: inserted ID
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute(INSERT_DEVICE, {'name': device_name,})
            if logger is not None:
                logger.debug("ADD_DEVICE")
            did = cursor.fetchone()[0]
        if logger is not None:
            logger.debug("id: {}, name: {}".format(did, device_name))
    except DatabaseError as err:
        if logger is not None:
            logger.warning("error device_name:{}, {}".format(device_name, err))
        # return default id
        did = 0
    return did


def truncate(conn, logger=None):
    """
    Truncate all record to t_weather.
    :param logger: application logger or None
    """
    global flag_truncating
    try:
        flag_truncating = False
        if logger is not None:
            logger.info("Truncate start.")
        with conn.cursor() as cursor:
            cursor.executescript(TRUNCATE_WEATHER)
    finally:
        flag_truncating = False
        if logger is not None:
            logger.info("Truncate finished.")


def insert(device_name, temp_out, temp_in, humid, pressure,
           measurement_time=None, conn=None, logger=None):
    """
    Insert weather sensor data to t_weather
    :param device_name: device name (required)
    :param temp_out: Outdoor Temperature (float or None)
    :param temp_in: Indoor Temperature (float or None)
    :param humid: humidity (float or None)
    :param pressure: pressure (float or None)
    :param measurement_time: timestamp with PostgreSQL
    :param conn: database connection
    :param logger: application logger or None
    """
    did = get_did(conn, device_name, logger=logger)
    rec = (did,
           measurement_time,
           to_float(temp_out),
           to_float(temp_in),
           to_float(humid),
           to_float(pressure)
           )
    if logger is not None:
        logger.debug(rec)
    try:
        with conn.cursor() as cursor:
            cursor.execute(INSERT_WEATHER,
                           {
                               'did': rec[0],
                               'measurement_time': rec[1],
                               'temp_out': rec[2],
                               'temp_in': rec[3],
                               'humid': rec[4],
                               'pressure': rec[5],
                            })
    except DatabaseError as err:
        if logger is not None:
            logger.warning("rec: {}\nerror:{}".format(rec, err))
