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

    # Check if tools are installed
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
        print("Tools not found. Installing dependencies...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "ruff", "pytest"], check=True
        )

    # 1. Format (Ruff)
    run_command([sys.executable, "-m", "ruff", "format", "."], "Formatting code")

    # 2. Lint & Fix (Ruff)
    lint_success = run_command(
        [sys.executable, "-m", "ruff", "check", ".", "--fix"],
        "Linting & Fixing code",
    )

    # 3. Test (Pytest)
    if os.path.isdir("tests"):
        test_success = run_command(
            [sys.executable, "-m", "pytest", "tests", "-p", "no:cacheprovider"],
            "Running tests",
        )
    else:
        print("INFO: 'tests' directory not found. Skipping tests.")
        test_success = True

    if not lint_success or not test_success:
        print("\nChecks completed with issues.")
        sys.exit(1)
    else:
        print("\nAll checks passed! Code is clean.")
        sys.exit(0)


if __name__ == "__main__":
    main()
