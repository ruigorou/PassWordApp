import os
import tempfile

# 実際のデータと混ざらないよう、アプリ起動前に一時フォルダを保存先にする
os.environ["FLET_APP_STORAGE_DATA"] = tempfile.mkdtemp(prefix="passwordapp-ui-")
