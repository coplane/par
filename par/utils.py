"""Simplified utilities for par"""

import hashlib
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import typer


def run_cmd(
    command: List[str],
    cwd: Optional[Path | str] = None,
    check: bool = True,
    capture: bool = True,
    suppress_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run a shell command with simplified error handling."""
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=capture,
            text=True,
            check=check,
            env=os.environ.copy(),
        )
        return result
    except subprocess.CalledProcessError as e:
        if not suppress_output:
            typer.secho(f"Command failed: {' '.join(command)}", fg="red", err=True)
            if e.stderr:
                typer.secho(e.stderr.strip(), fg="red", err=True)
        raise
    except FileNotFoundError:
        typer.secho(f"Command not found: {command[0]}", fg="red", err=True)
        raise typer.Exit(127)


def get_git_repo_root() -> Path:
    """Get the root directory of the current git repository."""
    try:
        result = run_cmd(
            ["git", "rev-parse", "--show-toplevel"],
            capture=True,
            suppress_output=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, typer.Exit):
        typer.secho("Error: Not in a git repository.", fg="red", err=True)
        typer.secho(
            "Please run par commands from within a git repository.", fg="red", err=True
        )
        raise typer.Exit(1)


def get_data_dir() -> Path:
    """Get par's data directory."""
    xdg_data_home = os.getenv("XDG_DATA_HOME")
    if xdg_data_home:
        data_dir = Path(xdg_data_home) / "par"
    else:
        data_dir = Path.home() / ".local" / "share" / "par"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _get_repo_id(repo_root: Path) -> str:
    """Generate a unique ID for the repository."""
    return hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:8]


def get_worktree_path(repo_root: Path, label: str) -> Path:
    """Get the path for a worktree."""
    repo_id = _get_repo_id(repo_root)
    worktrees_dir = get_data_dir() / "worktrees" / repo_id
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    return worktrees_dir / label


def get_tmux_session_name(repo_root: Path, label: str) -> str:
    """Generate a tmux session name."""
    repo_name = repo_root.name.lower().replace(" ", "-").replace(".", "-")[:15]
    repo_id = _get_repo_id(repo_root)[:4]
    return f"par-{repo_name}-{repo_id}-{label}"


def get_repo_id(repo_root: Path) -> str:  # New function
    """Generates a unique, filesystem-friendly ID for the repository."""
    return hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:12]


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
