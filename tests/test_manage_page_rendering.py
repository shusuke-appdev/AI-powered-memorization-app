from streamlit.testing.v1 import AppTest

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
