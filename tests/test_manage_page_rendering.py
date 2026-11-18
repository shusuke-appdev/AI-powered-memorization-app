from streamlit.testing.v1 import AppTest

from pages.manage_page import _matching_sources

_MANAGE_SCRIPT = r"""
import streamlit as st
import pages.manage_page as manage

def load_cards(user_id, category):
    st.session_state["loaded_cards_category"] = category
    return [{"id": "card-1", "category": category, "source_id": None}]

def load_sources(user_id, category):
    st.session_state["loaded_sources_category"] = category
    return []

def render_category(user_id, category, *args):
    st.session_state["rendered_categories"] = [category]

manage.load_cards_by_category = load_cards
manage.load_source_cards_by_category = load_sources
manage._render_category_tab = render_category
manage.render_manage_page("user-a")
"""


def test_manage_page_loads_and_renders_only_selected_category() -> None:
    app = AppTest.from_string(_MANAGE_SCRIPT).run()

    selected = app.selectbox(key="manage_category").value
    assert app.session_state["loaded_cards_category"] == selected
    assert app.session_state["loaded_sources_category"] == selected
    assert app.session_state["rendered_categories"] == [selected]

    app = app.selectbox(key="manage_category").select("刑法").run()
    assert app.session_state["loaded_cards_category"] == "刑法"
    assert app.session_state["loaded_sources_category"] == "刑法"
    assert app.session_state["rendered_categories"] == ["刑法"]


def test_search_finds_linked_question_and_answer_and_null_category() -> None:
    source = {
        "id": "source-1",
        "category": None,
        "card_type": "知識",
        "source_text": "元の本文",
        "title": "旧データ",
    }
    linked = {"source-1": [{"question": "検索対象の問題", "answer": "特別な答え"}]}

    assert _matching_sources([source], linked, "その他", "すべて", "検索対象") == [
        source
    ]
    assert _matching_sources([source], linked, "その他", "すべて", "特別な答え") == [
        source
    ]
    assert _matching_sources([source], linked, "民法", "すべて", "特別な答え") == []


_SEARCH_SCRIPT = r"""
import importlib
import streamlit as st
import pages.manage_page as manage

manage = importlib.reload(manage)

def load_cards(user_id, category):
    return [{
        "id": "card-1", "source_id": "source-1", "category": "その他",
        "card_type": "知識", "question": "検索対象の問題", "answer": "特別な答え",
    }] if category == "その他" else []

def load_sources(user_id, category):
    st.session_state["visible_sources"] = []
    return [{
        "id": "source-1", "category": None, "card_type": "知識",
        "source_text": "元の本文", "title": "旧データ",
    }] if category == "その他" else []

def render_source(user_id, source, linked_cards, category):
    st.session_state["visible_sources"].append(source["id"])

manage.load_cards_by_category = load_cards
manage.load_source_cards_by_category = load_sources
manage._render_source_card_expander = render_source
manage.render_manage_page("user-a")
"""


def test_manage_page_renders_linked_answer_search_result() -> None:
    app = AppTest.from_string(_SEARCH_SCRIPT).run()
    app = app.selectbox(key="manage_category").select("その他").run()
    app = app.text_input(key="unified_search").input("特別な答え").run()

    assert app.session_state["visible_sources"] == ["source-1"]


_REGENERATION_SCRIPT = r"""
import importlib
import streamlit as st
from application_errors import PersistenceError
import pages.manage_page as manage

manage = importlib.reload(manage)
source = {
    "id": "source-1", "category": "民法", "card_type": "規範",
    "source_text": "元の【穴】", "title": "架空の原文",
}
manage.load_cards_by_category = lambda *args: []
manage.load_source_cards_by_category = lambda *args: [source]

def save(user, **payload):
    st.session_state["test_save_payload"] = payload
    if st.session_state.get("test_fail"):
        raise PersistenceError("テスト用の保存失敗")

manage.replace_source_cards = save
manage.render_manage_page("user-a")
"""


def test_regeneration_saves_all_pages_and_keeps_failed_edits() -> None:
    app = AppTest.from_string(_REGENERATION_SCRIPT).run()
    source = "について検討する。".join(f"【項目{i}】" for i in range(100))
    app.text_area(key="edit_source_source-1").input(source).run()
    app.button(key="regen_source-1").click().run()

    nodes = list(app)
    save_index = next(
        i
        for i, element in enumerate(nodes)
        if getattr(element, "label", "") == "全20枚を上書き保存"
    )
    edit_index = next(
        i for i, element in enumerate(nodes) if getattr(element, "label", "") == "問題"
    )
    assert save_index < edit_index
    assert len([widget for widget in app.text_area if widget.form_id]) == 2
    next(widget for widget in app.text_area if widget.label == "答え").input(
        "先頭を編集"
    )
    next(button for button in app.button if button.label == "次のカード").click().run()
    next(widget for widget in app.text_area if widget.label == "答え").input(
        "2枚目を編集"
    )
    app.session_state["test_fail"] = True
    next(
        button for button in app.button if button.label == "全20枚を上書き保存"
    ).click().run()
    assert app.warning[0].value == "テスト用の保存失敗"
    assert (
        next(widget for widget in app.text_area if widget.label == "答え").value
        == "2枚目を編集"
    )
    payload = app.session_state["test_save_payload"]
    assert len(payload["cards"]) == 20
    assert payload["cards"][0]["answer"] == "先頭を編集"
    assert payload["cards"][1]["answer"] == "2枚目を編集"
    assert payload["expected"]["source"]["source_text"] == "元の【穴】"
    app.session_state["test_fail"] = False
    next(
        button for button in app.button if button.label == "全20枚を上書き保存"
    ).click().run()
    assert app.success[0].value == "再生成したカードを保存しました。"
