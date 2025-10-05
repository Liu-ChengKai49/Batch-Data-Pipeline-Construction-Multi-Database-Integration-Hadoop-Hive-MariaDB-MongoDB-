import os, sqlalchemy as sa
MARIADB_URL = os.getenv("MARIADB_URL") or \
    f"mysql+pymysql://{os.getenv('MARIADB_USER','root')}:{os.getenv('MARIADB_PASSWORD','')}" \
    f"@{os.getenv('MARIADB_HOST','mariadb')}:{os.getenv('MARIADB_PORT','3306')}/{os.getenv('MARIADB_DB','market')}"
engine = sa.create_engine(MARIADB_URL, pool_pre_ping=True, future=True)