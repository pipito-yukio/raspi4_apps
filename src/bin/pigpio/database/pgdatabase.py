import json
import psycopg2


class PgDatabase(object):
    def __init__(self, configfile, hostname, readonly=False, autocommit=False, logger=None):
        self.logger = logger
        with open(configfile, 'r') as fp:
            dbconf = json.load(fp)

        # replace real lower hostname in dbconf["host"] = {hostname}.local
        dbconf["host"] = dbconf["host"].format(hostname=hostname) #"format(**{'hostname':hostname})
        if self.logger is not None:
            self.logger.debug(f"dbconf: {dbconf}")
        # default connection is itarable curosr
        self.conn = psycopg2.connect(**dbconf)
        self.conn.set_session(readonly=readonly, autocommit=autocommit)
        if self.logger is not None:
            self.logger.info(self.conn)

    def get_connection(self):
        return self.conn

    def close(self):
        if self.conn is not None:
            self.logger.info("Close {} ".format(self.conn))
            try:
                self.conn.close()
            except:
                pass
