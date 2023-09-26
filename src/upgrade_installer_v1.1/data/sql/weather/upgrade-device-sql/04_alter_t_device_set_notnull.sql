-- t_deviceテーブルのdescription(説明)列をNOT NULLに設定する
-- 最初の列追加では既存のデータのdescription列がNULLのため NOT NULL にできない
-- 列追加後に既存のレコードのdescription列更新スクリプトを実行したあとに NOT NULL制約を付与する
ALTER TABLE weather.t_device ALTER COLUMN description SET NOT NULL;

