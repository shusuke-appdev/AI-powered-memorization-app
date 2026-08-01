from types import SimpleNamespace
from unittest.mock import Mock, patch

from auth import (
    MAINTENANCE_USERNAME,
    get_all_users,
    get_or_create_maintenance_user,
    register_user,
)


def test_register_user_rejects_whitespace_only_name_without_db_call() -> None:
    with patch("auth.get_supabase") as get_supabase:
        success, message, user_id = register_user("   ")

    assert success is False
    assert "入力" in message
    assert user_id is None
    get_supabase.assert_not_called()


def test_register_user_rejects_reserved_maintenance_name_case_insensitively() -> None:
    with patch("auth.get_supabase") as get_supabase:
        success, message, user_id = register_user(" CODEX-MAINTENANCE ")

    assert success is False
    assert "使用できません" in message
    assert user_id is None
    get_supabase.assert_not_called()


def test_register_user_rejects_name_longer_than_fifty_characters() -> None:
    success, message, user_id = register_user("a" * 51)

    assert success is False
    assert "50文字" in message
    assert user_id is None


def test_get_all_users_hides_maintenance_user_by_default() -> None:
    query = Mock()
    query.select.return_value = query
    query.execute.return_value = SimpleNamespace(
        data=[
            {"id": "1", "username": "shusuke"},
            {"id": "2", "username": MAINTENANCE_USERNAME},
        ]
    )
    supabase = Mock()
    supabase.table.return_value = query

    with patch("auth.get_supabase", return_value=supabase):
        users = get_all_users()

    assert users == [{"id": "1", "username": "shusuke"}]


def test_get_all_users_can_include_maintenance_user() -> None:
    all_users = [
        {"id": "1", "username": "shusuke"},
        {"id": "2", "username": MAINTENANCE_USERNAME},
    ]
    query = Mock()
    query.select.return_value = query
    query.execute.return_value = SimpleNamespace(data=all_users)
    supabase = Mock()
    supabase.table.return_value = query

    with patch("auth.get_supabase", return_value=supabase):
        users = get_all_users(include_maintenance=True)

    assert users == all_users


def test_get_or_create_maintenance_user_reuses_existing_user() -> None:
    query = Mock()
    query.select.return_value = query
    query.ilike.return_value = query
    query.execute.return_value = SimpleNamespace(
        data=[{"id": "2", "username": MAINTENANCE_USERNAME}]
    )
    supabase = Mock()
    supabase.table.return_value = query

    with patch("auth.get_supabase", return_value=supabase):
        user = get_or_create_maintenance_user()

    assert user == {"id": "2", "username": MAINTENANCE_USERNAME}
    query.insert.assert_not_called()


def test_get_or_create_maintenance_user_creates_missing_user() -> None:
    select_query = Mock()
    select_query.select.return_value = select_query
    select_query.ilike.return_value = select_query
    select_query.execute.return_value = SimpleNamespace(data=[])

    insert_query = Mock()
    insert_query.insert.return_value = insert_query
    insert_query.execute.return_value = SimpleNamespace(
        data=[{"id": "3", "username": MAINTENANCE_USERNAME}]
    )

    supabase = Mock()
    supabase.table.side_effect = [select_query, insert_query]

    with patch("auth.get_supabase", return_value=supabase):
        user = get_or_create_maintenance_user()

    assert user == {"id": "3", "username": MAINTENANCE_USERNAME}
    insert_payload = insert_query.insert.call_args.args[0]
    assert insert_payload["username"] == MAINTENANCE_USERNAME
    assert insert_payload["password_hash"].startswith("password_disabled_")
