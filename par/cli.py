# src/par/cli.py
import importlib.metadata
from typing import List, Optional

import typer
from typing_extensions import Annotated

from . import core, workspace

app = typer.Typer(
    name="par",
    help="Manage parallel git worktrees and tmux sessions.",
)


def get_session_labels() -> List[str]:
    """Get list of all session and workspace labels for autocomplete."""
    try:
        # All sessions now include workspaces (with session_type="workspace")
        sessions = core._get_all_sessions()
        return list(sessions.keys())
    except Exception:
        return []


def version_callback(value: bool):
    if value:
        try:
            version = importlib.metadata.version("par-cli")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown (not installed)"
        typer.echo(f"par version: {version}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
):
    """
    Par: Parallel Worktree & Tmux Manager
    """
    pass


@app.command()
def start(
    label: Annotated[
        str,
        typer.Argument(
            help="A globally unique label for the new worktree, branch, and tmux session."
        ),
    ],
    path: Annotated[
        Optional[str],
        typer.Option(
            "--path", "-p",
            help="Path to git repository (defaults to current directory)"
        ),
    ] = None,
    open_session: Annotated[
        bool,
        typer.Option(
            "--open", help="Automatically open/attach to the session after creation."
        ),
    ] = False,
):
    """
    Start a new git worktree and tmux session.
    Creates a worktree, a git branch (both named <label>), and a tmux session.
    Labels must be globally unique across all repositories.
    """
    core.start_session(label, repo_path=path, open_session=open_session)


def get_session_labels_with_all() -> List[str]:
    """Get list of all session and workspace labels plus 'all' for autocomplete."""
    try:
        labels = get_session_labels()  # Reuse the unified function
        labels.append("all")
        return labels
    except Exception:
        return ["all"]


@app.command()
def send(
    target: Annotated[
        str,
        typer.Argument(
            help="The label of the session to send the command to, or 'all'.",
            autocompletion=get_session_labels_with_all,
        ),
    ],
    command_to_send: Annotated[
        str, typer.Argument(help="The command string to send to the tmux session(s).")
    ],
):
    """
    Send a command to a specific session or all sessions.
    The command will be followed by an 'Enter' key press in the tmux session.
    """
    core.send_command(target, command_to_send)


@app.command(name="ls")
def list_sessions():
    """
    List all 'par'-managed sessions for the current repository.
    Shows label, tmux session name, worktree path, and branch.
    """
    core.list_sessions()


@app.command()
def rm(
    target: Annotated[
        str,
        typer.Argument(
            help="The label of the session to remove, or 'all'.",
            autocompletion=get_session_labels_with_all,
        ),
    ],
):
    """
    Remove a 'par'-managed session (or all sessions).
    This kills the tmux session, removes the git worktree, and deletes the associated git branch.
    """
    if target.lower() == "all":
        core.remove_all_sessions()
    else:
        core.remove_session(target)


@app.command()
def checkout(
    target: Annotated[
        str,
        typer.Argument(
            help="Branch name, PR number (pr/123), PR URL, or remote branch (user:branch)"
        ),
    ],
    path: Annotated[
        Optional[str],
        typer.Option(
            "--path", "-p",
            help="Path to git repository (defaults to current directory)"
        ),
    ] = None,
    label: Annotated[
        Optional[str],
        typer.Option(
            "--label",
            "-l",
            help="Custom globally unique label for the session (defaults to branch name)",
        ),
    ] = None,
):
    """
    Checkout an existing branch or PR into a new par session.
    Creates a worktree from existing branch/PR without creating a new branch.
    Labels must be globally unique across all repositories.
    """
    core.checkout_session(target, custom_label=label, repo_path=path)


@app.command()
def open(
    label: Annotated[
        str,
        typer.Argument(
            help="The label of the session to open/attach to. Use '-' to open the last session.",
            autocompletion=get_session_labels,
        ),
    ],
):
    """
    Open/attach to a specific 'par'-managed tmux session.
    If inside tmux, switches client. If outside, attaches.
    Use '-' to open the last session you had open.
    Short alias: 'o'
    """
    core.open_session(label)


@app.command(hidden=True)
def o(
    label: Annotated[
        str,
        typer.Argument(
            help="The label of the session to open/attach to. Use '-' to open the last session.",
            autocompletion=get_session_labels,
        ),
    ],
):
    """
    Alias for 'open'. Open/attach to a specific 'par'-managed tmux session.
    Use '-' to open the last session you had open.
    """
    core.open_session(label)


@app.command(name="control-center")
def control_center():
    """
    Create a new 'control-center' tmux session with separate windows for each par session.
    Must be run from outside tmux. Shows all sessions and workspaces globally.
    """
    core.open_control_center()


# Workspace commands
workspace_app = typer.Typer(help="Manage multi-repository workspaces")
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("start")
def workspace_start(
    label: Annotated[
        str,
        typer.Argument(help="A globally unique label for the workspace"),
    ],
    path: Annotated[
        Optional[str],
        typer.Option(
            "--path", "-p",
            help="Path to workspace directory (defaults to current directory)"
        ),
    ] = None,
    repos: Annotated[
        Optional[str],
        typer.Option(
            "--repos",
            "-r",
            help="Comma-separated repository names (auto-detects if not specified)",
        ),
    ] = None,
    open_session: Annotated[
        bool,
        typer.Option("--open", help="Automatically open the workspace after creation"),
    ] = False,
):
    """
    Start a new multi-repository workspace.
    Creates worktrees and branches for multiple repos in a single tmux session.
    Labels must be globally unique across all repositories and workspaces.
    """
    # Parse comma-separated repos
    repo_list = None
    if repos:
        repo_list = [r.strip() for r in repos.split(",") if r.strip()]

    workspace.start_workspace_session(label, workspace_path=path, repos=repo_list, open_session=open_session)


@workspace_app.command("ls")
def workspace_list():
    """
    List all workspace sessions for the current directory.
    """
    workspace.list_workspace_sessions()


@workspace_app.command("open")
def workspace_open(
    label: Annotated[str, typer.Argument(help="The label of the workspace to open")],
):
    """
    Open/attach to a specific workspace session.
    """
    workspace.open_workspace_session(label)


@workspace_app.command("code")
def workspace_code(
    label: Annotated[
        str, typer.Argument(help="The label of the workspace to open in VSCode")
    ],
):
    """
    Open a workspace in VSCode with all repositories.
    """
    workspace.open_workspace_in_ide(label, "code")


@workspace_app.command("cursor")
def workspace_cursor(
    label: Annotated[
        str, typer.Argument(help="The label of the workspace to open in Cursor")
    ],
):
    """
    Open a workspace in Cursor with all repositories.
    """
    workspace.open_workspace_in_ide(label, "cursor")


@workspace_app.command("rm")
def workspace_remove(
    target: Annotated[
        str, typer.Argument(help="The label of the workspace to remove, or 'all'")
    ],
):
    """
    Remove a workspace session (or all workspace sessions).
    This removes all worktrees, branches, and the tmux session.
    """
    if target.lower() == "all":
        workspace.remove_all_workspace_sessions()
    else:
        workspace.remove_workspace_session(target)


# This is for `python -m par`
if __name__ == "__main__":
    app()
