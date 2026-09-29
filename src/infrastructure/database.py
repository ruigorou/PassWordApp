import sqlite3

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_meta (
  id             INTEGER PRIMARY KEY CHECK (id = 1),
  kdf_salt       BLOB    NOT NULL,
  kdf_n          INTEGER NOT NULL,
  kdf_r          INTEGER NOT NULL,
  kdf_p          INTEGER NOT NULL,
  verifier       BLOB    NOT NULL,
  schema_version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS credentials (
  id         TEXT PRIMARY KEY,
  payload    BLOB NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    # 鍵導出を別スレッドで行うため check_same_thread=False。書き込みは UI から逐次行う
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
