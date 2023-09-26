import os
import signal
import socket
from datetime import datetime
import db.weatherdb as wdb
from log import logsetting
from database.pgdatabase import PgDatabase 

"""
raspi-4 UDP packet Monitor from ESP Weather sensors With Insert sensors_pgdb on PostgreSQL
[UDP port] 2222
"""

# args option default
WEATHER_UDP_PORT = 2222
BUFF_SIZE = 1024
PATH_CONF = os.path.join(os.environ.get("PATH_LOGGER_CONF", os.path.expanduser("~/bin/pigpio/conf")))
PATH_DBCONN_FILE = os.path.join(PATH_CONF, "dbconf.json")


def detect_signal(signum, frame):
    """
    Detect shutdown, and execute cleanup.
    :param signum: Signal number
    :param frame: frame
    :return:
    """
    logger.info("signum: {}, frame: {}".format(signum, frame))
    if signum == signal.SIGTERM or signum == signal.SIGSTOP:
        # signal shutdown
        cleanup()
        # Current process terminate
        exit(0)


def cleanup():
    pgdb.close()
    udp_client.close()


def loop(client, conn):
    server_ip = ''
    while True:
        data, addr = client.recvfrom(BUFF_SIZE)
        if server_ip != addr:
            server_ip = addr
            logger.info("server ip: {}".format(server_ip))

        # from ESP output: device_name, temp_out, temp_in, humid, pressure
        line = data.decode("utf-8")
        record = line.split(",")
        # Insert weather DB with local time
        logger.debug(line)
        # PostgreSQL timestamp.
        now_timestamp = datetime.now()
        s_timestamp = now_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        wdb.insert(*record, measurement_time=s_timestamp, conn=conn, logger=logger)


if __name__ == '__main__':
    # PostgreSQL database
    global pgdb

    logger = logsetting.create_logger("service_weather") # only fileHandler

    hostname = socket.gethostname()
    # Receive broadcast.
    broad_address = ("", WEATHER_UDP_PORT)
    logger.info("{}: {}".format(hostname, broad_address))
    # UDP client
    udp_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_client.bind(broad_address)
    
    # Insert immediately commit.
    pgdb = PgDatabase(PATH_DBCONN_FILE, hostname, readonly=False, autocommit=True, logger=logger);
    conn = pgdb.get_connection()
    try:
        # load device cache
        wdb.load_device_cache(conn=conn, logger=logger)
        loop(udp_client, conn)
    except KeyboardInterrupt:
        pass
    finally:
        pgdb.close()
        cleanup()
