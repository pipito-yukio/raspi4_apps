CREATE ROLE developer WITH LOGIN PASSWORD 'abcdefg';
--install pgcrypto that is required superuser. 
ALTER ROLE developer WITH SUPERUSER;
CREATE DATABASE sensors_pgdb WITH OWNER=developer ENCODING='UTF-8' LC_COLLATE='ja_JP.UTF-8' LC_CTYPE='ja_JP.UTF-8' TEMPLATE=template0;
GRANT ALL PRIVILEGES ON DATABASE sensors_pgdb TO developer;
