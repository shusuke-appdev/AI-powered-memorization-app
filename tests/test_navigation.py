from streamlit.testing.v1 import AppTest

_NAVIGATION_SCRIPT = r"""
import streamlit as st
import pages.navigation as navigation

def renderer(name):
    def render(user_id):
        st.session_state.setdefault("rendered_pages", []).append(name)
    return render

navigation.render_review_page = renderer("review")
navigation.render_add_card_page = renderer("add")
navigation.render_listen_page = renderer("listen")
navigation.render_manage_page = renderer("manage")
navigation.render_stats_page = renderer("stats")
st.navigation(navigation.build_authenticated_pages("user-a"), position="top").run()
"""


def test_navigation_executes_only_selected_page_renderer() -> None:
    app = AppTest.from_string(_NAVIGATION_SCRIPT).run()
    assert app.session_state["rendered_pages"] == ["review"]


def test_login_navigation_reserves_all_public_urls() -> None:
    script = """
import pages.navigation as navigation
import streamlit as st
navigation.show_login_page = lambda: st.write("login-only")
pages = navigation.build_login_pages()
st.session_state["login_paths"] = [page.url_path for page in pages]
st.navigation(pages, position="hidden").run()
"""
    app = AppTest.from_string(script).run()
    assert [markdown.value for markdown in app.markdown] == ["login-only"]
    assert app.session_state["login_paths"] == [
        "",
        "add",
        "listen",
        "manage",
        "stats",
    ]
