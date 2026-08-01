import os
import subprocess
import sys


def run_command(command: list[str], description: str) -> bool:
    """検証コマンドを実行し、成否を返す。"""
    print(f"\n[Code Factory] Executing: {description}...")
    try:
        # Run command and show output directly to user/agent
        result = subprocess.run(command, check=False, text=True)
        if result.returncode != 0:
            print(f"FAILED: {description} failed or found issues.")
            return False
        print(f"PASSED: {description} passed.")
        return True
    except Exception as e:
        print(f"ERROR executing {description}: {e}")
        return False


def main() -> None:
    """プロジェクトの基本的な整形・lint・テストを実行する。"""
    print("Starting Code Factory Lite checks...")

    # Check if tools are installed. CI/local checks must not install or rewrite.
    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "--version"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Tools not found. Run: python -m pip install -r requirements.txt")
        sys.exit(1)

    # 1. Dependency consistency
    dependency_success = run_command(
        [sys.executable, "-m", "pip", "check"],
        "Checking dependency consistency",
    )

    # 2. Compile
    compile_success = run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "app.py",
            "auth.py",
            "components.py",
            "config.py",
            "database.py",
            "export_import.py",
            "stats.py",
            "storage.py",
            "pages",
            "services",
            "scripts",
            "use_cases",
            "tests",
        ],
        "Compiling Python sources",
    )

    # 3. Format check (Ruff)
    format_success = run_command(
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        "Checking code format",
    )

    # 4. Lint (Ruff)
    lint_success = run_command(
        [sys.executable, "-m", "ruff", "check", "."],
        "Linting code",
    )

    # 5. Test (Pytest)
    if os.path.isdir("tests"):
        test_success = run_command(
            [sys.executable, "-m", "pytest", "tests", "-p", "no:cacheprovider", "-q"],
            "Running tests",
        )
    else:
        print("INFO: 'tests' directory not found. Skipping tests.")
        test_success = True

    if not all(
        (
            dependency_success,
            compile_success,
            format_success,
            lint_success,
            test_success,
        )
    ):
        print("\nChecks completed with issues.")
        sys.exit(1)
    else:
        print("\nAll checks passed! Code is clean.")
        sys.exit(0)


if __name__ == "__main__":
    main()
