-- t_deviceテーブルにdescription(説明)列を追加する
-- クライアントアプリ側でリストボックスなどの見出しに利用するため
ALTER TABLE weather.t_device ADD COLUMN description VARCHAR(128);

