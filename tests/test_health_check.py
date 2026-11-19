import hashlib
import io
import json
import socket
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import urlparse

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


def test_published_release_checks_routes_assets_and_anonymous_rpc() -> None:
    app = "https://study.example.test"
    db = "https://fixture.supabase.co"
    public_key = "sb_publishable_examplefixture1234567890"
    assets = {
        "assets/index.js": f"console.log('{db}', '{public_key}');".encode(),
        "assets/index.css": b"body{color:#242424}",
    }
    index = b'<script src="/assets/index.js"></script><link href="/assets/index.css">'
    release = {
        "revision": "1" * 40,
        "index": hashlib.sha256(index).hexdigest(),
        "assets": {
            name: hashlib.sha256(data).hexdigest() for name, data in assets.items()
        },
    }
    paths: list[str] = []

    def request(resource, timeout):
        assert timeout == 10
        assert resource.get_header("User-agent") == "memorization-app-health/1.0"
        url = resource.full_url
        path = urlparse(url).path
        paths.append(path)
        if path in ("/auth/v1/settings", "/rest/v1/rpc/study_api"):
            assert resource.get_header("Apikey") == public_key
        if path == "/rest/v1/rpc/study_api":
            assert json.loads(resource.data)["p_action"] == "quota_view"
            raise HTTPError(url, 403, "Forbidden", {}, None)
        content = {
            "/release.json": json.dumps(release).encode(),
            "/auth/v1/settings": b'{"external":{"google":true}}',
            **{"/" + name: data for name, data in assets.items()},
        }
        result = io.BytesIO(content.get(path, index))
        result.headers = {"Content-Security-Policy": "default-src 'self'"}
        result.geturl = lambda: app + "/review"
        return result

    with patch("scripts.health_check.urlopen", side_effect=request):
        assert health_check.check_published_app(app, db).ok
        assert "/listen/" in paths
        assert "/practice" in paths
        assert "/assets/index.css" in paths
        assets["assets/index.css"] = b"tampered"
        assert (
            health_check.check_published_app(app, db).exit_code == health_check.EXIT_APP
        )
