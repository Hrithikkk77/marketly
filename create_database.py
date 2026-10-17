"""Creates the MySQL database and app user from your .env values.
Run once:  python create_database.py   (it asks for your MySQL admin password)"""
import getpass
import os
import re
import sys

import pymysql
from dotenv import load_dotenv

load_dotenv()
host = os.environ["DB_HOST"]
port = int(os.environ.get("DB_PORT", "3306"))
db_name, app_user, app_pw = os.environ["DB_NAME"], os.environ["DB_USER"], os.environ["DB_PASSWORD"]
if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
    sys.exit("DB_NAME may only contain letters, numbers and underscores.")

admin_user = input("MySQL admin username [root]: ").strip() or "root"
admin_pw = getpass.getpass("MySQL admin password: ")
try:
    conn = pymysql.connect(host=host, port=port, user=admin_user, password=admin_pw)
except pymysql.err.OperationalError as e:
    sys.exit(f"Could not connect to MySQL at {host}:{port}: {e}\n"
             "Check that MySQL is running and the admin password is right.")

scope = "localhost" if host in ("127.0.0.1", "localhost") else "%"
with conn.cursor() as c:
    c.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    c.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (app_user, scope, app_pw))
    c.execute("ALTER USER %s@%s IDENTIFIED BY %s", (app_user, scope, app_pw))
    c.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO %s@%s", (app_user, scope))
    c.execute("FLUSH PRIVILEGES")
conn.commit()
conn.close()
print(f"Done. Database '{db_name}' and user '{app_user}' are ready.")
