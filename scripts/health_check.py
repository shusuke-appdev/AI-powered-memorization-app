"""Read-only operational health check for GitHub CLI and Supabase."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

import tomllib

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_DNS = 3
EXIT_SUPABASE = 4
EXIT_GITHUB_CLI = 5
EXIT_GITHUB_AUTH = 6
EXIT_GITHUB_API = 7


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    message: str
    exit_code: int = EXIT_OK


def _load_local_secrets(secrets_path: Path) -> dict[str, str]:
    if not secrets_path.exists():
        return {}

    secrets = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    loaded: dict[str, str] = {}
    for name in ("SUPABASE_URL", "SUPABASE_KEY"):
        value = secrets.get(name)
        if isinstance(value, str):
            loaded[name] = value
    return loaded


def load_supabase_credentials(
    environ: Mapping[str, str] | None = None,
    secrets_path: Path = Path(".streamlit/secrets.toml"),
) -> tuple[str, str]:
    env = os.environ if environ is None else environ
    local_secrets = _load_local_secrets(secrets_path)

    url = env.get("SUPABASE_URL") or local_secrets.get("SUPABASE_URL", "")
    key = env.get("SUPABASE_KEY") or local_secrets.get("SUPABASE_KEY", "")
    return url, key


def check_supabase_credentials(url: str, key: str) -> CheckResult:
    if not url or not key:
        return CheckResult(
            ok=False,
            message=(
                "SUPABASE_URL または SUPABASE_KEY が未設定です。"
                "GitHub Actions では repository secrets を確認してください。"
            ),
            exit_code=EXIT_CONFIG,
        )
    return CheckResult(ok=True, message="Supabase credentials are configured.")


def check_supabase_dns(url: str) -> CheckResult:
    hostname = urlparse(url).hostname
    if not hostname:
        return CheckResult(
            ok=False,
            message="SUPABASE_URL のホスト名を読み取れません。",
            exit_code=EXIT_CONFIG,
        )

    try:
        socket.getaddrinfo(hostname, 443)
    except socket.gaierror:
        return CheckResult(
            ok=False,
            message=(
                "Supabase のホスト名を DNS 解決できません。"
                "Free Plan のプロジェクトが停止している可能性があります。"
            ),
            exit_code=EXIT_DNS,
        )

    return CheckResult(ok=True, message="Supabase DNS resolved.")


def check_supabase_read(url: str, key: str) -> CheckResult:
    try:
        from supabase import create_client

        client = create_client(url, key)
        client.table("users").select("id").limit(1).execute()
    except Exception as error:
        return CheckResult(
            ok=False,
            message=f"Supabase の読み取り確認に失敗しました: {type(error).__name__}",
            exit_code=EXIT_SUPABASE,
        )

    return CheckResult(ok=True, message="Supabase read check passed.")


def _run_gh(
    args: list[str], env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=30,
        env=dict(env),
    )


def check_github_cli(environ: Mapping[str, str] | None = None) -> CheckResult:
    env = os.environ if environ is None else environ

    try:
        version = _run_gh(["--version"], env)
    except FileNotFoundError:
        return CheckResult(
            ok=False,
            message="GitHub CLI gh が見つかりません。",
            exit_code=EXIT_GITHUB_CLI,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            ok=False,
            message="GitHub CLI gh の起動がタイムアウトしました。",
            exit_code=EXIT_GITHUB_CLI,
        )

    if version.returncode != 0:
        return CheckResult(
            ok=False,
            message="GitHub CLI gh の起動確認に失敗しました。",
            exit_code=EXIT_GITHUB_CLI,
        )

    auth = _run_gh(["auth", "status"], env)
    if auth.returncode != 0:
        return CheckResult(
            ok=False,
            message="GitHub CLI gh の認証状態を確認できません。",
            exit_code=EXIT_GITHUB_AUTH,
        )

    if env.get("GITHUB_ACTIONS", "").lower() == "true":
        repository = env.get("GITHUB_REPOSITORY", "")
        if not env.get("GH_TOKEN") or not repository:
            return CheckResult(
                ok=False,
                message="GitHub Actions の GH_TOKEN または GITHUB_REPOSITORY が未設定です。",
                exit_code=EXIT_GITHUB_API,
            )

        api = _run_gh(["api", f"repos/{repository}/actions/workflows", "--silent"], env)
        if api.returncode != 0:
            return CheckResult(
                ok=False,
                message="GitHub Actions から GitHub API へ接続できません。",
                exit_code=EXIT_GITHUB_API,
            )

    return CheckResult(ok=True, message="GitHub CLI/API check passed.")


def run_health_check(
    environ: Mapping[str, str] | None = None,
    secrets_path: Path = Path(".streamlit/secrets.toml"),
) -> list[CheckResult]:
    url, key = load_supabase_credentials(environ=environ, secrets_path=secrets_path)
    results = [check_supabase_credentials(url, key)]

    if results[-1].ok:
        results.append(check_supabase_dns(url))
    if results[-1].ok:
        results.append(check_supabase_read(url, key))

    results.append(check_github_cli(environ=environ))
    return results


def main() -> int:
    results = run_health_check()
    for result in results:
        prefix = "OK" if result.ok else "FAILED"
        print(f"{prefix}: {result.message}")

    failed = [result for result in results if not result.ok]
    if failed:
        return failed[0].exit_code

    print("HEALTH_CHECK_OK: Supabase and GitHub CLI/API checks passed.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
