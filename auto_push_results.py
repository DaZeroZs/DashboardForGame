import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path


# 🔁 EXTERNE Datei (wird beobachtet)
SOURCE_FILE = Path("../data/challenge_leaderboard.json")

# 📦 Ziel im aktuellen Repo
TARGET_FILE = Path("challenge_leaderboard.json")

CHECK_INTERVAL = 5  # seconds
COMMIT_MESSAGE_PREFIX = "Update results"


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=False
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def ensure_git_repo(repo_dir: Path) -> None:
    code, out, err = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], repo_dir)
    if code != 0:
        raise RuntimeError(f"Not a git repository: {repo_dir}\n{err}")


def git_commit_and_push(repo_dir: Path, file_path: Path) -> None:
    rel_path = file_path.relative_to(repo_dir)

    code, out, err = run_cmd(["git", "add", str(rel_path)], repo_dir)
    if code != 0:
        raise RuntimeError(f"git add failed:\n{err}")

    code, out, err = run_cmd(["git", "diff", "--cached", "--quiet"], repo_dir)
    if code == 0:
        print("No staged changes to commit.")
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"{COMMIT_MESSAGE_PREFIX} ({timestamp})"

    code, out, err = run_cmd(["git", "commit", "-m", commit_message], repo_dir)
    if code != 0:
        raise RuntimeError(f"git commit failed:\n{err}")

    print(f"Committed: {commit_message}")

    code, out, err = run_cmd(["git", "push"], repo_dir)
    if code != 0:
        raise RuntimeError(f"git push failed:\n{err}")

    print("Pushed to remote successfully.")


def main():
    repo_dir = Path(__file__).resolve().parent

    try:
        ensure_git_repo(repo_dir)
    except Exception as e:
        print(e)
        sys.exit(1)

    source_file = SOURCE_FILE.resolve()
    target_file = (repo_dir / TARGET_FILE).resolve()

    print(f"Watching: {source_file}")
    print(f"Target:   {target_file}")
    print(f"Check interval: {CHECK_INTERVAL}s")

    last_hash = file_hash(source_file)

    while True:
        try:
            current_hash = file_hash(source_file)

            if current_hash is None:
                print("Source file not found, waiting...")

            elif last_hash is None:
                print("File appeared. Copying + uploading...")
                shutil.copy2(source_file, target_file)
                git_commit_and_push(repo_dir, target_file)
                last_hash = current_hash

            elif current_hash != last_hash:
                print("Change detected. Copying + uploading...")
                shutil.copy2(source_file, target_file)
                git_commit_and_push(repo_dir, target_file)
                last_hash = current_hash

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopped.")
            break

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()