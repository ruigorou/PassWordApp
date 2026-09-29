class DomainError(Exception):
    """業務ルール違反。message は画面にそのまま表示できる文言。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


class CredentialNotFoundError(DomainError):
    def __init__(self):
        super().__init__("データが見つかりません")
