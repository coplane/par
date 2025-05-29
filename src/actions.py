# src/par/actions.py

import typer

from . import git, tmux, utils  # Use git and tmux to refer to our modules
from .manager import SessionManager


def start_new_session(label: str):
    manager = SessionManager()
    if manager.get_session(label):
        typer.secho(
            f"Error: A session with label '{label}' already exists for this repository.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    repo_root = utils.get_git_repo_root()
    worktree_path = utils.get_worktree_path(repo_root, label)
    tmux_session_name = utils.get_tmux_session_name(repo_root, label)
    branch_name = label  # Git branch will be the same as the label

    if worktree_path.exists():
        typer.secho(
            f"Error: Worktree path '{worktree_path}' already exists. Please remove it or choose a different label.",
            fg=typer.colors.RED,
            err=True,
        )
        # Consider offering to clean it up or adopt it. For now, fail.
        raise typer.Exit(1)

    if tmux.session_exists(tmux_session_name):
        typer.secho(
            f"Error: tmux session '{tmux_session_name}' already exists. Please kill it or choose a different label.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    git.create_worktree(label=branch_name, worktree_path=worktree_path)
    tmux.create_session(session_name=tmux_session_name, worktree_path=worktree_path)

    manager.add_session(label, worktree_path, tmux_session_name, branch_name)
    typer.secho(
        f"Successfully started session '{label}'.",
        fg=typer.colors.BRIGHT_GREEN,
        bold=True,
    )
    typer.echo(f"  Git Worktree: {worktree_path}")
    typer.echo(f"  Git Branch: {branch_name}")
    typer.echo(f"  Tmux Session: {tmux_session_name}")
    typer.echo(f"To open: par open {label}")


def remove_session_action(label: str):
    repo_root = (
        utils.get_git_repo_root()
    )  # Get current repo context for stale artifact paths
    manager = SessionManager()
    session_data = manager.get_session(label)  # Scoped to current repo

    if not session_data:
        typer.secho(
            f"Warning: Session '{label}' not found in 'par' state for this repository.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            f"Attempting to clean up potential stale artifacts for '{label}' in repo '{repo_root.name}'..."
        )
        # Construct paths and names based on current repo context
        stale_worktree_path = utils.get_worktree_path(repo_root, label)
        stale_tmux_session = utils.get_tmux_session_name(repo_root, label)
        stale_branch_name = label  # Branch name is just the label

        tmux.kill_session(stale_tmux_session)
        git.remove_worktree(
            stale_worktree_path
        )  # remove_worktree also removes the dir if it exists
        git.delete_branch(stale_branch_name)

        # The manager.remove_session(label) call below (if session_data existed)
        # would also try to remove the physical dir. Here, we've done it via Tgit.remove_worktree.
        # No need to call manager.remove_session again if it wasn't found in the first place.
        typer.secho(f"Cleanup attempt for '{label}' finished.", fg=typer.colors.CYAN)
        return


def remove_all_sessions_action():
    manager = SessionManager()
    sessions = manager.get_all_sessions_for_current_repo()
    if not sessions:
        typer.secho(
            "No active sessions for this repository to remove.", fg=typer.colors.YELLOW
        )
        return

    typer.confirm(
        f"Are you sure you want to remove all {len(sessions)} sessions for this repository?",
        abort=True,
    )

    for session in sessions:
        typer.echo(f"Removing session '{session['label']}'...")
        remove_session_action(session["label"])  # Call the single remove action
    typer.secho(
        "All sessions for this repository removed.",
        fg=typer.colors.BRIGHT_GREEN,
        bold=True,
    )


def send_command_to_sessions(target_label: str, command_to_send: str):
    manager = SessionManager()
    if target_label.lower() == "all":
        sessions = manager.get_all_sessions_for_current_repo()
        if not sessions:
            typer.secho(
                "No active sessions to send command to.", fg=typer.colors.YELLOW
            )
            return
        for session_data in sessions:
            typer.echo(
                f"Sending to '{session_data['label']}' (session: {session_data['tmux_session_name']})..."
            )
            tmux.send_keys(session_data["tmux_session_name"], command_to_send)
    else:
        session_data = manager.get_session(target_label)
        if not session_data:
            typer.secho(
                f"Error: Session '{target_label}' not found.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(
            f"Sending to '{target_label}' (session: {session_data['tmux_session_name']})..."
        )
        tmux.send_keys(session_data["tmux_session_name"], command_to_send)


def list_sessions_action():
    manager = SessionManager()
    sessions = manager.get_all_sessions_for_current_repo()
    if not sessions:
        typer.secho(
            "No active sessions managed by 'par' for this repository.",
            fg=typer.colors.YELLOW,
        )
        return

    typer.secho("Managed 'par' sessions for this repository:", bold=True)
    from rich.console import Console
    from rich.table import Table

    table = Table(title="Par Sessions")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Tmux Session", style="magenta")
    table.add_column("Branch", style="green")
    table.add_column("Worktree Path", style="blue")
    table.add_column("Created At (UTC)", style="dim")

    for session in sorted(sessions, key=lambda s: s["label"]):
        # Verify tmux session exists
        session_active_tmux = (
            "✅" if tmux.session_exists(session["tmux_session_name"]) else "❌"
        )

        table.add_row(
            session["label"],
            f"{session['tmux_session_name']} ({session_active_tmux})",
            session["branch_name"],
            session["worktree_path"],
            session["created_at"],
        )

    console = Console()
    console.print(table)


def open_session_action(label: str):
    manager = SessionManager()
    session_data = manager.get_session(label)
    if not session_data:
        typer.secho(
            f"Error: Session '{label}' not found.", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(1)

    tmux_session_name = session_data["tmux_session_name"]
    if not tmux.session_exists(tmux_session_name):
        typer.secho(
            f"Error: tmux session '{tmux_session_name}' for label '{label}' does not exist. It might have been killed manually.",
            fg=typer.colors.RED,
            err=True,
        )
        typer.echo(
            "You might need to remove and recreate this par session: `par rm {label}` then `par start {label}`"
        )
        raise typer.Exit(1)

    tmux.open_session_in_client(tmux_session_name)


def open_control_center_action():
    manager = SessionManager()
    sessions = manager.get_all_sessions_for_current_repo()

    active_sessions_data = []
    for s_data in sessions:
        if tmux.session_exists(s_data["tmux_session_name"]):
            active_sessions_data.append(s_data)
        else:
            typer.secho(
                f"Warning: Tmux session for label '{s_data['label']}' ({s_data['tmux_session_name']}) not found. Skipping for control center.",
                fg=typer.colors.YELLOW,
            )

    if not active_sessions_data:
        typer.secho(
            "No currently active tmux sessions managed by 'par' to display in control center.",
            fg=typer.colors.YELLOW,
        )
        return

    tmux.open_all_sessions_in_control_center(active_sessions_data)
