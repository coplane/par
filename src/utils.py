import hashlib
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import typer


def run_cmd(
    command: List[str],
    cwd: Optional[Path | str] = None,
    check: bool = True,
    capture: bool = True,
    env: Optional[Dict[str, str]] = None,
    suppress_output: bool = False,
) -> subprocess.CompletedProcess:
    """Runs a shell command."""
    if not suppress_output:
        # For debugging, consider using a logger or a verbose flag
        # typer.echo(f"Running: {' '.join(command)}{f' in {cwd}' if cwd else ''}", err=True)
        pass
    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=capture,
            text=True,
            check=check,
            env=process_env,
        )
        return result
    except subprocess.CalledProcessError as e:
        if not suppress_output:
            typer.secho(
                f"Error running command: {' '.join(command)}",
                fg=typer.colors.RED,
                err=True,
            )
            if e.stdout:
                typer.secho(f"STDOUT:\n{e.stdout}", fg=typer.colors.YELLOW, err=True)
            if e.stderr:
                typer.secho(f"STDERR:\n{e.stderr}", fg=typer.colors.RED, err=True)
        raise
    except FileNotFoundError:
        typer.secho(
            f"Error: Command '{command[0]}' not found.", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=127)


_git_repo_root_cache: Optional[Path] = None  # Keep this as is


def get_git_repo_root() -> Path:
    """Gets the root directory of the current git repository."""
    global _git_repo_root_cache
    # Invalidate cache if CWD changed significantly (e.g., to a different repo)
    # A simple check: if cached, verify it's still a git repo and points to the same path
    if _git_repo_root_cache:
        try:
            current_root_check_cmd = run_cmd(
                ["git", "rev-parse", "--show-toplevel"],
                capture=True,
                suppress_output=True,
                cwd=Path.cwd(),
            )
            if Path(current_root_check_cmd.stdout.strip()) == _git_repo_root_cache:
                return _git_repo_root_cache
            else:  # Current CWD is in a different git repo or not a git repo
                _git_repo_root_cache = None
        except (
            subprocess.CalledProcessError,
            typer.Exit,
        ):  # Not a git repo or other error
            _git_repo_root_cache = None

    if _git_repo_root_cache is None:
        try:
            # Always determine from current working directory for freshness
            result = run_cmd(
                ["git", "rev-parse", "--show-toplevel"],
                capture=True,
                suppress_output=True,
                cwd=Path.cwd(),
            )
            _git_repo_root_cache = Path(result.stdout.strip())
        except (subprocess.CalledProcessError, typer.Exit):
            typer.secho(
                "Error: Not inside a git repository, or 'git' command failed.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Please navigate to a git repository to use 'par' commands that require repository context.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
    return _git_repo_root_cache


def get_repo_id(repo_root: Path) -> str:  # New function
    """Generates a unique, filesystem-friendly ID for the repository."""
    return hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:12]


def get_data_dir() -> Path:  # (ensure it exists)
    """Gets the application's data directory."""
    xdg_data_home = os.getenv("XDG_DATA_HOME")
    if xdg_data_home:
        data_dir = Path(xdg_data_home) / "par"
    else:
        data_dir = Path.home() / ".local" / "share" / "par"
    data_dir.mkdir(parents=True, exist_ok=True)  # Ensure it's created
    return data_dir


def get_worktrees_base_dir() -> Path:  # New function (ensure it exists)
    """Gets the base directory for storing all par worktrees."""
    d = get_data_dir() / "worktrees"
    d.mkdir(parents=True, exist_ok=True)  # Ensure it's created
    return d


def get_repo_worktrees_dir(repo_root: Path) -> Path:  # New function (ensure it exists)
    """Gets the directory for storing worktrees for a specific repository."""
    repo_id_str = get_repo_id(repo_root)
    d = get_worktrees_base_dir() / repo_id_str
    d.mkdir(parents=True, exist_ok=True)  # Ensure it's created
    return d


def get_worktree_path(repo_root: Path, label: str) -> Path:  # Updated
    """Gets the path for a specific worktree within its repository's namespaced folder."""
    return get_repo_worktrees_dir(repo_root) / label


def is_tmux_running() -> bool:
    """Checks if a tmux server is running."""
    try:
        run_cmd(
            ["tmux", "has-session"], check=False, capture=True, suppress_output=True
        )
        return True  # has-session exits 0 if server running, 1 otherwise
    except typer.Exit:  # if tmux command not found
        return False
    except subprocess.CalledProcessError:  # Should not happen with check=False
        return False


TMUX_SESSION_PREFIX = "par"


def get_tmux_session_name(repo_root: Path, label: str) -> str:  # Updated
    """Generates the tmux session name, namespaced by repository."""
    # Using basename of repo_root for readability, plus part of hash for uniqueness if names collide
    repo_name_part = (
        repo_root.name.lower().replace(" ", "-").replace(".", "-")[:15]
    )  # Sanitize and shorten
    repo_hash_part = get_repo_id(repo_root)[:4]  # Short hash part
    return f"{TMUX_SESSION_PREFIX}-{repo_name_part}-{repo_hash_part}-{label}"
