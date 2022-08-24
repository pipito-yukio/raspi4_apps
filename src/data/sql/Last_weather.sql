set search_path to weather;

SELECT
  *
FROM
  t_weather
WHERE
  measurement_time = (SELECT max(measurement_time) FROM t_weather WHERE did=(SELECT id FROM t_device WHERE name='esp8266_1'));
