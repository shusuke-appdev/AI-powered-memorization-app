import socket
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import scripts.health_check as health_check


def test_missing_supabase_secrets_fail_without_leaking_values(tmp_path: Path) -> None:
    results = health_check.run_health_check(
        environ={}, secrets_path=tmp_path / "missing"
    )

    assert results[0].exit_code == health_check.EXIT_CONFIG
    assert "SUPABASE_URL" in results[0].message
    assert "eyJ" not in results[0].message


def test_dns_failure_is_classified_as_project_stop_risk() -> None:
    with patch("scripts.health_check.socket.getaddrinfo", side_effect=socket.gaierror):
        result = health_check.check_supabase_dns("https://example.supabase.co")

    assert not result.ok
    assert result.exit_code == health_check.EXIT_DNS
    assert "停止している可能性" in result.message


def test_supabase_read_success() -> None:
    table = Mock()
    select = table.select.return_value
    limit = select.limit.return_value
    limit.execute.return_value = Mock(data=[])

    client = Mock()
    client.table.return_value = table

    with patch("supabase.create_client", return_value=client):
        result = health_check.check_supabase_read(
            "https://example.supabase.co",
            "secret-key",
        )

    assert result.ok
    client.table.assert_called_once_with("users")
    table.select.assert_called_once_with("id")
    select.limit.assert_called_once_with(1)
    limit.execute.assert_called_once_with()


def _completed(returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["gh"], returncode=returncode)


def test_github_cli_missing_is_classified() -> None:
    with patch("scripts.health_check._run_gh", side_effect=FileNotFoundError):
        result = health_check.check_github_cli(environ={})

    assert not result.ok
    assert result.exit_code == health_check.EXIT_GITHUB_CLI


def test_github_auth_failure_is_classified() -> None:
    with patch(
        "scripts.health_check._run_gh",
        side_effect=[_completed(0), _completed(1)],
    ):
        result = health_check.check_github_cli(environ={})

    assert not result.ok
    assert result.exit_code == health_check.EXIT_GITHUB_AUTH


def test_github_actions_api_failure_is_classified() -> None:
    environ = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "owner/repo",
        "GH_TOKEN": "token",
    }
    with patch(
        "scripts.health_check._run_gh",
        side_effect=[_completed(0), _completed(0), _completed(1)],
    ):
        result = health_check.check_github_cli(environ=environ)

    assert not result.ok
    assert result.exit_code == health_check.EXIT_GITHUB_API


def test_github_actions_api_success() -> None:
    environ = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "owner/repo",
        "GH_TOKEN": "token",
    }
    with patch(
        "scripts.health_check._run_gh",
        side_effect=[_completed(0), _completed(0), _completed(0)],
    ):
        result = health_check.check_github_cli(environ=environ)

    assert result.ok
