# src/par/cli.py
from typing import List, Optional

import typer
from typing_extensions import Annotated

from . import core, workspace

app = typer.Typer(
    name="par",
    help="Manage parallel git worktrees and tmux sessions.",
)


def get_session_labels() -> List[str]:
    """Get list of session and workspace labels for autocomplete."""
    try:
        labels = []

        # Add single-repo sessions
        sessions = core._get_repo_sessions()
        labels.extend(sessions.keys())

        # Add workspaces that contain current repo
        current_repo_root = core.utils.get_git_repo_root()
        current_repo_name = current_repo_root.name
        current_dir = current_repo_root.parent
        workspace_sessions = workspace._get_workspace_sessions(current_dir)

        for ws_label, ws_data in workspace_sessions.items():
            # Check if this workspace contains the current repository
            for repo_data in ws_data.get("repos", []):
                if repo_data["repo_name"] == current_repo_name:
                    labels.append(ws_label)
                    break

        return labels
    except Exception:
        return []


def version_callback(value: bool):
    if value:
        typer.echo("par version: 0.1.0")
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
            help="A unique label for the new worktree, branch, and tmux session."
        ),
    ],
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
    """
    core.start_session(label, open_session=open_session)


def get_session_labels_with_all() -> List[str]:
    """Get list of session and workspace labels plus 'all' for autocomplete."""
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
    label: Annotated[
        Optional[str],
        typer.Option(
            "--label",
            "-l",
            help="Custom label for the session (defaults to branch name)",
        ),
    ] = None,
):
    """
    Checkout an existing branch or PR into a new par session.
    Creates a worktree from existing branch/PR without creating a new branch.
    """
    core.checkout_session(target, label)


@app.command()
def open(
    label: Annotated[
        str,
        typer.Argument(
            help="The label of the session to open/attach to.",
            autocompletion=get_session_labels,
        ),
    ],
):
    """
    Open/attach to a specific 'par'-managed tmux session.
    If inside tmux, switches client. If outside, attaches.
    """
    core.open_session(label)


@app.command(name="control-center")
def control_center():
    """
    Open all 'par'-managed sessions in a tiled tmux window (control center view).
    Must be run from within an existing tmux session.
    """
    core.open_control_center()


# Workspace commands
workspace_app = typer.Typer(help="Manage multi-repository workspaces")
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("start")
def workspace_start(
    label: Annotated[
        str,
        typer.Argument(help="A unique label for the workspace"),
    ],
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
    """
    # Parse comma-separated repos
    repo_list = None
    if repos:
        repo_list = [r.strip() for r in repos.split(",") if r.strip()]

    workspace.start_workspace_session(label, repo_list, open_session)


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
