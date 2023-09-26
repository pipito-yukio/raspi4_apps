\connect sensors_pgdb

CREATE SCHEMA IF NOT EXISTS weather;

CREATE TABLE IF NOT EXISTS weather.t_device(
   id INTEGER NOT NULL,
   name VARCHAR(20) UNIQUE NOT NULL,
   CONSTRAINT pk_device PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS weather.t_weather(
   did INTEGER NOT NULL,
   measurement_time timestamp NOT NULL,
   temp_out REAL,
   temp_in REAL,
   humid REAL,
   pressure REAL
);

ALTER TABLE weather.t_weather ADD CONSTRAINT pk_weather PRIMARY KEY (did, measurement_time);

ALTER TABLE weather.t_weather ADD CONSTRAINT fk_device FOREIGN KEY (did) REFERENCES weather.t_device (id);

ALTER SCHEMA weather OWNER TO developer;
ALTER TABLE weather.t_device OWNER TO developer;
ALTER TABLE weather.t_weather OWNER TO developer;
