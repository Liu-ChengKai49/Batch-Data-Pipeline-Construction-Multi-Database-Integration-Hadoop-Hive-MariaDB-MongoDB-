# bi/sheets_sync/export_to_sheets.py
import os
import pandas as pd
import sqlalchemy as sa
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Connection URL resolution ---
# Prefer MARIA_URL (what your Makefile passes), otherwise fall back to MARIADB_URL,
# otherwise build from individual pieces with sensible defaults.
MARIADB_URL = (
    os.getenv("MARIA_URL")
    or os.getenv("MARIADB_URL")
    or (
        "mysql+pymysql://"
        f"{os.getenv('MARIADB_USER','root')}:"
        f"{os.getenv('MARIADB_PASSWORD','')}"
        f"@{os.getenv('MARIADB_HOST','mariadb')}:"
        f"{os.getenv('MARIADB_PORT','3306')}/"
        f"{os.getenv('MARIADB_DB','market')}"
    )
)

SHEETS_DOC_ID = os.environ["SHEETS_DOC_ID"]
# Expect a FILE PATH to the service account JSON inside the container
SA_PATH = os.environ.get("GOOGLE_SA_JSON", "bi/sheets_sync/service_account.json")

# 1) read marts/views
engine = sa.create_engine(MARIADB_URL, pool_pre_ping=True, future=True)

# If your URL already selects the right schema (e.g., /demo), these unqualified
# view names will work. Otherwise, qualify them, e.g. "demo.prices_daily".
prices = pd.read_sql("SELECT * FROM vw_prices_daily", engine)
symbols = pd.read_sql("SELECT * FROM vw_symbols_dim", engine)

# 2) auth
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name(SA_PATH, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEETS_DOC_ID)

def write_tab(tab_name: str, df: pd.DataFrame):
    try:
        ws = sh.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows="100", cols="26")
    ws.clear()
    # convert datetimes to ISO strings
    df = df.copy()
    for c in df.columns:
        if str(df[c].dtype).startswith("datetime"):
            df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d")
    ws.update([df.columns.tolist()] + df.astype(str).values.tolist())

write_tab("prices_daily", prices)
write_tab("symbols_dim", symbols)
print("SHEETS_SYNC_OK")
