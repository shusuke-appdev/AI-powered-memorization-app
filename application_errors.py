"""利用者向けに安全なアプリケーション例外。"""

from __future__ import annotations


class ApplicationError(Exception):
    """画面へ安全に表示できる既知のアプリケーション例外。"""

    default_message = "処理を完了できませんでした。もう一度お試しください。"

    def __init__(self, message: str | None = None) -> None:
        self.user_message = message or self.default_message
        super().__init__(self.user_message)


class ValidationError(ApplicationError):
    """入力値がアプリの保存条件を満たしていない。"""

    default_message = "入力内容を確認してください。"


class RecordNotFoundError(ApplicationError):
    """更新対象が存在しないか、現在のユーザーに属していない。"""

    default_message = "対象データが見つかりません。画面を再読み込みしてください。"


class MigrationUnavailableError(ApplicationError):
    """互換対象のDB migrationがまだ導入されていない。"""

    default_message = "データベースの更新がまだ完了していません。"


class PersistenceError(ApplicationError):
    """DB書き込みを安全に完了できなかった。"""

    default_message = "保存に失敗しました。時間をおいてもう一度お試しください。"
