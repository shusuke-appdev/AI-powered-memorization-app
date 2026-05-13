"""
AI サービスモジュール — Gemini API操作の統合管理
新SDK (google-genai) を使用。APIキーごとにClientインスタンスをキャッシュ。
"""

from __future__ import annotations

import json
import re
from typing import Any

from google import genai
from google.genai import types

from config import GEMINI_MODEL

# ============ APIエラー例外 ============


class GeminiAPIError(Exception):
    """Gemini API 共通エラー"""


class QuotaExceededError(GeminiAPIError):
    """API利用制限超過エラー"""

    def __init__(self) -> None:
        super().__init__(
            "APIの無料枠利用制限に達しました。しばらく待ってから再試行するか、別のAPIキーを使用してください。"
        )


# ============ 共通ユーティリティ ============


def check_quota_error(error: Exception) -> None:
    """APIエラーがquota超過かチェックし、該当する場合はQuotaExceededErrorを送出"""
    error_str = str(error).lower()
    if any(kw in error_str for kw in ("quota", "rate", "limit", "429")):
        raise QuotaExceededError() from error


# ============ Gemini クライアント（シングルトン） ============

_clients: dict[str, genai.Client] = {}


def _get_client(api_key: str) -> genai.Client:
    """APIキーに対応するClientインスタンスを取得（キャッシュ付き）"""
    if api_key not in _clients:
        _clients[api_key] = genai.Client(api_key=api_key)
    return _clients[api_key]


def _get_json_config(
    *, temperature: float = 0.0, top_p: float = 0.95
) -> types.GenerateContentConfig:
    """JSON出力用の生成設定を取得"""
    return types.GenerateContentConfig(
        temperature=temperature,
        top_p=top_p,
        response_mime_type="application/json",
    )





# ============ ヘルプAIチャット ============


def _load_help_context() -> str:
    """HELP_AI_CONTEXT.mdを読み込む"""
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # servicesディレクトリの親（プロジェクトルート）から読み込む
    context_path = os.path.join(os.path.dirname(script_dir), "HELP_AI_CONTEXT.md")

    try:
        with open(context_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"ヘルプコンテキスト読み込みエラー: {e}")
        return ""


def help_chat(
    user_question: str, api_key: str, chat_history: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    """
    アプリのヘルプAIチャットボット

    Args:
        user_question: ユーザーの質問
        api_key: Gemini APIキー
        chat_history: 過去のチャット履歴

    Returns:
        dict: {"success": bool, "response": str, "error": str (optional)}
    """
    if not api_key:
        return {
            "success": False,
            "error": "APIキーが設定されていません。左側のメニューからAPIキーを設定してください。",
        }

    if not user_question or not user_question.strip():
        return {"success": False, "error": "質問を入力してください。"}

    try:
        client = _get_client(api_key)
        help_context = _load_help_context()

        system_prompt = f"""あなたは「AI暗記カード」アプリのヘルプアシスタントです。
ユーザーからの質問に、以下のアプリ情報を元に回答してください。

【重要なルール】
1. このアプリに関係する質問にのみ回答してください
2. アプリに関係ない質問（天気、雑談、他のアプリについてなど）には丁寧にお断りしてください
3. 回答は簡潔にしてください（2-3文程度が理想）
4. 専門用語は分かりやすく説明してください
5. 手順を説明する際は箇条書きを使ってください

【アプリ情報】
{help_context}
"""

        # チャット履歴を構築
        history: list[types.Content] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=system_prompt + "\n\n（以下がユーザーとの会話です）")],
            ),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text="了解しました。AI暗記カードアプリのヘルプアシスタントとして、ご質問にお答えします。")],
            ),
        ]

        if chat_history:
            for msg in chat_history:
                role = "user" if msg.get("role") == "user" else "model"
                history.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg.get("content", ""))],
                    )
                )

        chat = client.chats.create(model=GEMINI_MODEL, history=history)
        response = chat.send_message(user_question)

        return {"success": True, "response": response.text}

    except Exception as e:
        check_quota_error(e)
        print(f"ヘルプAIエラー: {e}")
        return {"success": False, "error": f"エラーが発生しました: {e!s}"}
