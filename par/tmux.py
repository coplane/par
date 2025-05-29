# src/par/Ttmux.py
import os
from pathlib import Path
from typing import List

import typer

from .utils import is_tmux_running, run_cmd


def check_tmux_env():
    if not is_tmux_running():
        typer.secho(
            "tmux server is not running. Please start tmux first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def create_session(session_name: str, worktree_path: Path):
    """Creates a new detached tmux session."""
    check_tmux_env()
    cmd = ["tmux", "new-session", "-d", "-s", session_name, "-c", str(worktree_path)]
    try:
        run_cmd(cmd)
        typer.secho(
            f"tmux session '{session_name}' created, starting in '{worktree_path}'.",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        typer.secho(
            f"Failed to create tmux session '{session_name}': {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def kill_session(session_name: str):
    """Kills a tmux session."""
    check_tmux_env()
    cmd = ["tmux", "kill-session", "-t", session_name]
    try:
        run_cmd(
            cmd, check=False, suppress_output=True
        )  # Don't fail if session doesn't exist
        typer.secho(
            f"tmux session '{session_name}' killed (if it existed).",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        typer.secho(
            f"Note: Error trying to kill tmux session '{session_name}': {e}",
            fg=typer.colors.YELLOW,
            err=True,
        )


def send_keys(session_name: str, command: str, pane: str = "0"):
    """Sends keys (a command) to a tmux session's pane."""
    check_tmux_env()
    target = f"{session_name}:{pane}"
    # Escape single quotes in the command for tmux send-keys
    cmd = ["tmux", "send-keys", "-t", target, command, "Enter"]
    try:
        run_cmd(cmd)
        typer.secho(
            f"Sent command to tmux session '{session_name}'.", fg=typer.colors.CYAN
        )
    except Exception as e:
        typer.secho(
            f"Failed to send command to tmux session '{session_name}': {e}",
            fg=typer.colors.RED,
            err=True,
        )


def session_exists(session_name: str) -> bool:
    check_tmux_env()
    result = run_cmd(
        ["tmux", "has-session", "-t", session_name],
        check=False,
        capture=True,
        suppress_output=True,
    )
    return result.returncode == 0


def list_sessions_by_prefix(prefix: str) -> List[str]:
    check_tmux_env()
    try:
        result = run_cmd(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture=True,
            suppress_output=True,
        )
        all_sessions = (
            result.stdout.strip().split("\n") if result.stdout.strip() else []
        )
        return [s for s in all_sessions if s.startswith(prefix)]
    except Exception:
        return []


def open_session_in_client(session_name: str):
    """Attaches to or switches to a tmux session."""
    check_tmux_env()
    if os.getenv("TMUX"):  # Inside a tmux session
        typer.echo(f"Switching to session '{session_name}' in current tmux client...")
        run_cmd(["tmux", "switch-client", "-t", session_name])
    else:  # Outside tmux
        typer.echo(f"Attaching to session '{session_name}'...")
        # We use os.execvp to replace the current process with tmux
        # This makes it behave like a direct `tmux attach`
        try:
            os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])
        except FileNotFoundError:
            typer.secho("Error: tmux command not found.", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.secho(
                f"Failed to attach to session '{session_name}': {e}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)


def open_all_sessions_in_control_center(sessions_data: List[dict]):
    """Opens all sessions in a new tmux window with tiled panes."""
    check_tmux_env()
    if os.getenv("TMUX"):
        typer.secho(
            "Error: Control center can only be opened from outside a running tmux session.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if not sessions_data:
        typer.secho("No sessions to open in control center.", fg=typer.colors.YELLOW)
        return

    # Get repo root and create control center session name
    from .utils import get_git_repo_root, get_tmux_session_name

    repo_root = get_git_repo_root()
    cc_session_name = get_tmux_session_name(repo_root, "cc")

    # Check if session already exists
    if session_exists(cc_session_name):
        typer.secho(
            f"Control center session '{cc_session_name}' already exists, attaching to it.",
            fg=typer.colors.CYAN,
        )
        open_session_in_client(cc_session_name)
        return

    # Create new control center session
    first_session = sessions_data[0]
    create_session(cc_session_name, Path(first_session["worktree_path"]))

    # Set up first pane with command to attach to first session
    cmd_attach_first = (
        f"TMUX= tmux attach-session -t {first_session['tmux_session_name']}"
    )
    send_keys(cc_session_name, cmd_attach_first)

    # Split for other sessions
    for session_data in sessions_data[1:]:
        cmd_attach_other = (
            f"TMUX= tmux attach-session -t {session_data['tmux_session_name']}"
        )
        # Split horizontally (-h) and set working directory
        run_cmd(
            [
                "tmux",
                "split-window",
                "-h",
                "-t",
                cc_session_name,
                "-c",
                str(session_data["worktree_path"]),
            ]
        )
        send_keys(cc_session_name, cmd_attach_other)
        # Re-tile after each split to keep it balanced
        run_cmd(["tmux", "select-layout", "-t", cc_session_name, "tiled"])

    # Final tile layout and attach to the control center session
    run_cmd(["tmux", "select-layout", "-t", cc_session_name, "tiled"])

    typer.secho(
        f"Control center session '{cc_session_name}' created with {len(sessions_data)} panes.",
        fg=typer.colors.GREEN,
    )

    # Attach to the control center session
    open_session_in_client(cc_session_name)
