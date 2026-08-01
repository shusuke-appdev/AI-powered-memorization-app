from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from application_errors import PersistenceError, RecordNotFoundError
from storage import (
    get_source_cards_by_ids,
    import_backup_atomic_rpc,
    save_source_bundle_rpc,
    update_card_progress,
)


def test_source_batch_read_is_scoped_to_user() -> None:
    query = Mock()
    query.select.return_value = query
    query.in_.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(
        data=[{"id": "source-a", "user_id": "user-a"}]
    )
    supabase = Mock()
    supabase.table.return_value = query

    with patch("storage.get_supabase", return_value=supabase):
        rows = get_source_cards_by_ids("user-a", ["source-a"])

    assert rows == [{"id": "source-a", "user_id": "user-a"}]
    query.eq.assert_called_once_with("user_id", "user-a")


def test_zero_row_progress_update_is_not_reported_as_success() -> None:
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.select.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    supabase = Mock()
    supabase.table.return_value = query

    with patch("storage.get_supabase", return_value=supabase):
        with pytest.raises(RecordNotFoundError):
            update_card_progress(
                "user-a",
                "missing-card",
                {
                    "ease_factor": 2.5,
                    "interval": 1,
                    "repetitions": 1,
                    "next_review": "2026-08-02",
                },
            )


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda: save_source_bundle_rpc("user-a", {"mode": "create"}),
            "カードを保存できませんでした。",
        ),
        (
            lambda: import_backup_atomic_rpc(
                "user-a", source_cards=[], cards=[], reset_progress=False
            ),
            "バックアップを保存できませんでした。",
        ),
    ],
)
def test_rpc_backend_errors_are_classified_as_persistence_errors(
    call, message: str
) -> None:
    rpc = Mock()
    rpc.execute.side_effect = RuntimeError("backend detail must stay private")
    supabase = Mock()
    supabase.rpc.return_value = rpc

    with patch("storage.get_supabase", return_value=supabase):
        with pytest.raises(PersistenceError, match=message):
            call()
