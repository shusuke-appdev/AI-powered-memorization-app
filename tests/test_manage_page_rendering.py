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
