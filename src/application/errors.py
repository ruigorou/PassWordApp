import math


class ApplicationError(Exception):
    """ユースケースの失敗。message は画面にそのまま表示できる文言。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class WrongMasterPasswordError(ApplicationError):
    def __init__(self):
        super().__init__("マスターパスワードが違います")


class TooManyAttemptsError(ApplicationError):
    def __init__(self, retry_after: float):
        super().__init__(f"続けて失敗したため、{math.ceil(retry_after)}秒後に再試行してください")
        self.retry_after = retry_after


class VaultLockedError(ApplicationError):
    def __init__(self):
        super().__init__("ロックされています")


class VaultStateError(ApplicationError):
    pass


class BackupFormatError(ApplicationError):
    pass


class CorruptedDataError(ApplicationError):
    pass


class VaultBusyError(ApplicationError):
    def __init__(self):
        super().__init__("処理中です。しばらくお待ちください")
