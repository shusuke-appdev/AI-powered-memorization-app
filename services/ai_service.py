"""
AI サービスモジュール — Gemini API操作の統合管理
シングルトンパターンでAPI設定を1回だけ実行
"""

from __future__ import annotations

import json
import re
from typing import Any

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

_configured_keys: set[str] = set()


def _get_model(api_key: str) -> Any:
    """Gemini モデルを取得（APIキー設定を1回だけ実行）"""
    import google.generativeai as genai

    if api_key not in _configured_keys:
        genai.configure(api_key=api_key)
        _configured_keys.add(api_key)

    return genai.GenerativeModel(GEMINI_MODEL)


def _get_generation_config(
    *, temperature: float = 0.0, top_p: float = 0.95
) -> Any:
    """JSON出力用の生成設定を取得"""
    import google.generativeai as genai

    return genai.GenerationConfig(
        temperature=temperature,
        top_p=top_p,
        response_mime_type="application/json",
    )


# ============ AI文節分割 ============


def split_into_phrases(text: str, api_key: str) -> list[str] | dict[str, str]:
    """
    AIを使ってテキストを文節（意味のある単位）に分割

    Args:
        text: 分割するテキスト
        api_key: Gemini APIキー

    Returns:
        list: 文節のリスト、またはエラー情報のdict
    """
    if not api_key:
        return simple_split(text)

    try:
        model = _get_model(api_key)

        prompt = f"""以下のテキストを、暗記カード用の意味のまとまりに分割してください。

【文法的ルール】
1. 助詞（は、が、を、に、で、の、と、から、まで、より、へ等）は全て独立したブロックとして分割する
2. 句読点（。、）は独立したブロックとして分割する
3. 丸数字（①②③等）は独立したブロックとして分割する
4. 名詞句のまとまり:
   - 形容詞・形容動詞・連体詞 + 名詞 → 1ブロック
   - 名詞 + 名詞（複合語）→ 1ブロック
   - ただし「名詞＋の＋名詞」は「名詞」「の」「名詞」と分割する
4. 動詞句のまとまり:
   - 副詞 + 動詞/形容詞 → 1ブロック
   - 動詞 + 補助動詞 → 1ブロック
   - 動詞の活用語尾は動詞に含める
5. 格助詞相当の表現（による、として、に対して、において等）は独立したブロックとして分割する
6. 専門用語・法律用語・固有名詞は分割しない
7. 【重要】改行（\\n）やスペース（全角・半角）、記号（：「」等）は絶対に削除せず、そのまま独立したブロックとするか、前後のブロックに含めてください。分割されたブロックをすべて結合させると、入力テキストと完全に一致するようにしてください。

【例1】
入力: 「この点について、実行行為は構成要件的結果発生の現実的危険性を有する行為であり、かかる危険性は不作為によっても惹起されうるから、不作為も実行行為足りうる。」
出力: ["この点について", "、", "実行行為", "は", "構成要件的結果発生", "の", "現実的危険性", "を", "有する", "行為", "であり", "、", "かかる危険性", "は", "不作為", "によって", "も", "惹起されうる", "から", "、", "不作為", "も", "実行行為", "足りうる", "。"]

【例2】
入力: 「そこで、作為との構成要件的同価値性が認められる場合、すなわち、法的作為義務があったのにそれに違背し、作為が可能かつ容易であったのに作為をしなかった場合に限り、不作為にも実行行為性が認められると解する。」
出力: ["そこで", "、", "作為", "との", "構成要件的同価値性", "が", "認められる", "場合", "、", "すなわち", "、", "法的作為義務", "が", "あった", "のに", "それ", "に", "違背し", "、", "作為", "が", "可能", "かつ", "容易", "であった", "のに", "作為", "を", "しなかった", "場合", "に", "限り", "、", "不作為", "にも", "実行行為性", "が", "認められる", "と", "解する", "。"]

【テキスト】
{text}

【出力形式】
{{"phrases": ["ブロック1", "ブロック2", "。", ...]}}"""

        response = model.generate_content(
            prompt, generation_config=_get_generation_config()
        )

        result = json.loads(response.text)
        phrases = result.get("phrases", [])
        return phrases if phrases else simple_split(text)

    except QuotaExceededError:
        raise
    except Exception as e:
        check_quota_error(e)
        print(f"AI分割エラー: {e}")
        return simple_split(text)


def simple_split(text: str) -> list[str]:
    """句読点と改行で簡易分割（空白や改行を維持する）"""
    parts = re.split(r"([。、，．,.！!？?\n]+)", text)
    result: list[str] = []
    current = ""
    for part in parts:
        if not part:
            continue
        current += part
        if re.search(r"[。、，．,.！!？?\n]", part):
            result.append(current)
            current = ""

    if current:
        result.append(current)

    return result if result else [text]


# ============ AI穴埋め提案 ============

# 句読点・記号セット（穴埋め対象外）
PUNCTUATION_SET: frozenset[str] = frozenset({
    "。", "、", "，", "．", ",", ".", "！", "？", "!", "?",
    "：", ":", "；", ";", "「", "」", "（", "）", "(", ")",
})


def suggest_blanks(phrases: list[str], api_key: str) -> list[int] | dict[str, str]:
    """
    AIが穴埋めにすべき文節を提案

    Args:
        phrases: 文節のリスト
        api_key: Gemini APIキー

    Returns:
        list: 穴埋めにすべき文節のインデックスリスト、またはエラー情報のdict
    """
    if not api_key:
        return []

    try:
        model = _get_model(api_key)

        indexed_phrases: list[str] = []
        valid_indices: list[int] = []
        for i, p in enumerate(phrases):
            stripped_p = p.strip()
            if stripped_p and stripped_p not in PUNCTUATION_SET:
                indexed_phrases.append(f"{i}: {p}")
                valid_indices.append(i)

        prompt = f"""以下の文節リストから、暗記カードの穴埋めにすべき重要な文節を選んでください。

【文節リスト】
{chr(10).join(indexed_phrases)}

【選び方の基準】
- 専門用語、固有名詞、数字、年号など、暗記すべき重要な情報を含む文節
- 全体の20-40%程度を選択
- 最低1つ、最大でリストの半分程度
- 句読点（。、等）は選択しないこと

【出力形式】
{{"selected_indices": [0, 2, 5]}}  // 選んだ文節のインデックス番号"""

        response = model.generate_content(
            prompt,
            generation_config=_get_generation_config(temperature=0.2),
        )

        result = json.loads(response.text)
        selected = result.get("selected_indices", [])
        return [i for i in selected if i in valid_indices]

    except QuotaExceededError:
        raise
    except Exception as e:
        check_quota_error(e)
        print(f"AI提案エラー: {e}")
        return []


# ============ ヘルプAIチャット ============


def _load_help_context() -> str:
    """HELP_AI_CONTEXT.mdを読み込む"""
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # servicesディレクトリの親（プロジェクトルート）から読み込む
    context_path = os.path.join(os.path.dirname(script_dir), "HELP_AI_CONTEXT.md")

    try:
        with open(context_path, "r", encoding="utf-8") as f:
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
        model = _get_model(api_key)
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

        messages = [
            {
                "role": "user",
                "parts": [system_prompt + "\n\n（以下がユーザーとの会話です）"],
            },
            {
                "role": "model",
                "parts": [
                    "了解しました。AI暗記カードアプリのヘルプアシスタントとして、ご質問にお答えします。"
                ],
            },
        ]

        if chat_history:
            for msg in chat_history:
                role = "user" if msg.get("role") == "user" else "model"
                messages.append({"role": role, "parts": [msg.get("content", "")]})

        messages.append({"role": "user", "parts": [user_question]})

        chat = model.start_chat(history=messages[:-1])
        response = chat.send_message(user_question)

        return {"success": True, "response": response.text}

    except Exception as e:
        check_quota_error(e)
        print(f"ヘルプAIエラー: {e}")
        return {"success": False, "error": f"エラーが発生しました: {e!s}"}
