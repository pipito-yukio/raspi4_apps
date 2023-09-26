-- 既存レコードに説明列を追加する
UPDATE weather.t_device SET description='メインセンサー' WHERE name='esp8266_1';
COMMIT;

