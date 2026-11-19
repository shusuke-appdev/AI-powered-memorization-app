"""Read-only operational health check for the published app, GitHub and Supabase."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_DNS = 3
EXIT_SUPABASE = 4
EXIT_GITHUB_CLI = 5
EXIT_GITHUB_AUTH = 6
EXIT_GITHUB_API = 7
EXIT_APP = 8


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


def check_published_app(url: str, supabase_url: str) -> CheckResult:
    """Verify the release, Google provider and anonymous API boundary without signing in."""
    base = url.rstrip("/")
    user_agent = {"User-Agent": "memorization-app-health/1.0"}

    def public_page(path: str):
        return urlopen(Request(base + path, headers=user_agent), timeout=10)

    try:
        with public_page("/release.json") as response:
            release = json.load(response)
        if not re.fullmatch(r"[a-f0-9]{40}", release["revision"]):
            raise ValueError("invalid release identifier")
        pages = ("/", "/review", "/practice", "/manage", "/add", "/stats")
        with public_page("/") as response:
            index = response.read()
            if not response.headers.get("Content-Security-Policy"):
                raise ValueError("missing CSP")
        if hashlib.sha256(index).hexdigest() != release["index"]:
            raise ValueError("index differs from release")
        for path in pages[1:]:
            with public_page(path) as response:
                if response.read() != index:
                    raise ValueError("direct link differs from release")
        for path in ("/listen", "/listen/"):
            with public_page(path) as response:
                if urlparse(response.geturl()).path != "/review":
                    raise ValueError("retired link did not redirect")
        public_key = None
        assets = release["assets"]
        references = {
            path.decode() for path in re.findall(rb'["\']/(assets/[^"\']+)["\']', index)
        }
        if not references or not references.issubset(assets):
            raise ValueError("index assets missing from release")
        for filename, digest in assets.items():
            if not re.fullmatch(r"assets/[A-Za-z0-9_.-]+\.(js|css)", filename):
                raise ValueError("invalid asset reference")
            with public_page("/" + filename) as response:
                bundle = response.read()
            if hashlib.sha256(bundle).hexdigest() != digest:
                raise ValueError("asset differs from release")
            match = re.search(rb"sb_publishable_[A-Za-z0-9_-]{20,}", bundle)
            if match and supabase_url.rstrip("/").encode() in bundle:
                public_key = match.group().decode("ascii")
        if not public_key:
            raise ValueError("database configuration differs from deploy target")
        headers = {
            **user_agent,
            "apikey": public_key,
            "Content-Type": "application/json",
        }
        with urlopen(
            Request(supabase_url.rstrip("/") + "/auth/v1/settings", headers=headers),
            timeout=10,
        ) as response:
            if json.load(response).get("external", {}).get("google") is not True:
                raise ValueError("Google sign-in disabled")
        query = Request(
            supabase_url.rstrip("/") + "/rest/v1/rpc/study_api",
            data=b'{"p_action":"quota_view","p_payload":{}}',
            headers=headers,
        )
        try:
            with urlopen(query, timeout=10):
                raise ValueError("anonymous API returned data")
        except HTTPError as error:
            if error.code not in (401, 403):
                raise
    except (OSError, ValueError, KeyError, TypeError):
        return CheckResult(
            ok=False,
            message="公開アプリの配信・認証の確認に失敗しました。",
            exit_code=EXIT_APP,
        )
    return CheckResult(
        ok=True, message=f"Published app verified ({release['revision'][:8]})."
    )


def run_health_check(
    environ: Mapping[str, str] | None = None,
    secrets_path: Path = Path(".streamlit/secrets.toml"),
) -> list[CheckResult]:
    env = os.environ if environ is None else environ
    url, key = load_supabase_credentials(environ=env, secrets_path=secrets_path)
    results = [check_supabase_credentials(url, key)]

    if results[-1].ok:
        results.append(check_supabase_dns(url))
    if results[-1].ok:
        results.append(check_supabase_read(url, key))

    results.append(check_github_cli(environ=env))
    if app_url := env.get("APP_HEALTH_URL"):
        results.append(check_published_app(app_url, url))
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
