"""Workspace management for multi-repository development."""

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import core, initialization, operations, utils


# Simplified workspace management - now workspaces are just special sessions
def _validate_workspace_label_unique(label: str) -> bool:
    """Check if a workspace label is globally unique across all sessions."""
    return core._validate_label_unique(label)


def _add_workspace_session(workspace_data: Dict[str, Any]):
    """Add a workspace as a special type of session to global state."""
    # Mark as workspace type and add to sessions (not separate workspace state)
    workspace_data["session_type"] = "workspace"
    core._add_session(workspace_data)




# Workspace operations
def start_workspace_session(
    label: str, workspace_path: Optional[str] = None, repos: Optional[List[str]] = None, open_session: bool = False
):
    """Start a new workspace with multiple repositories."""
    # Validate label is globally unique
    if not _validate_workspace_label_unique(label):
        typer.secho(f"Error: Label '{label}' already exists. Labels must be globally unique.", fg="red", err=True)
        raise typer.Exit(1)

    # Resolve workspace directory
    if workspace_path:
        workspace_root = Path(workspace_path).resolve()
        if not workspace_root.exists():
            typer.secho(f"Error: Directory '{workspace_path}' does not exist.", fg="red", err=True)
            raise typer.Exit(1)
    else:
        workspace_root = Path.cwd()

    # Auto-detect repos if not specified
    if not repos:
        detected_repos = utils.detect_git_repos(workspace_root)
        if not detected_repos:
            typer.secho(
                f"Error: No git repositories found in {workspace_root}.",
                fg="red",
                err=True,
            )
            typer.echo("Use --repos to specify repositories explicitly.")
            raise typer.Exit(1)
        repo_names = [repo.name for repo in detected_repos]
        repo_paths = detected_repos
    else:
        repo_names = []
        repo_paths = []
        for repo_spec in repos:
            # Support both absolute paths and relative names
            if repo_spec.startswith('/') or Path(repo_spec).is_absolute():
                # Absolute path provided
                repo_path = Path(repo_spec).resolve()
                repo_name = repo_path.name
            else:
                # Relative name provided (traditional behavior)
                repo_name = repo_spec
                repo_path = workspace_root / repo_name

            if not repo_path.exists():
                typer.secho(
                    f"Error: Repository path '{repo_path}' does not exist.", fg="red", err=True
                )
                raise typer.Exit(1)
            if not (repo_path / ".git").exists():
                typer.secho(
                    f"Error: '{repo_path}' is not a git repository.", fg="red", err=True
                )
                raise typer.Exit(1)

            repo_names.append(repo_name)
            repo_paths.append(repo_path)

    session_name = utils.get_workspace_session_name(workspace_root, label)

    # Check for conflicts
    if operations.tmux_session_exists(session_name):
        typer.secho(f"Error: tmux session '{session_name}' exists.", fg="red", err=True)
        raise typer.Exit(1)

    # Create worktrees for each repo
    repos_data = []
    for repo_path, repo_name in zip(repo_paths, repo_names):
        worktree_path = utils.get_workspace_worktree_path(
            workspace_root, label, repo_name, label
        )

        # Check for conflicts
        if worktree_path.exists():
            typer.secho(
                f"Error: Worktree path '{worktree_path}' exists.", fg="red", err=True
            )
            raise typer.Exit(1)

        # Create resources
        operations.create_workspace_worktree(repo_path, label, worktree_path)

        # Copy includes for this repository
        config = initialization.load_par_config(repo_path)
        if config:
            initialization.copy_included_files(
                config, repo_path, worktree_path
            )

        repos_data.append(
            {
                "repo_name": repo_name,
                "repo_path": str(repo_path),
                "worktree_path": str(worktree_path),
                "branch_name": label,
            }
        )

    # Calculate workspace root directory
    first_worktree_path = Path(repos_data[0]["worktree_path"])
    workspace_root = first_worktree_path.parent.parent

    # Create simple tmux session starting from workspace root
    operations.create_tmux_session(session_name, workspace_root)

    # Run initialization for each repository if .par.yaml exists
    for repo_data in repos_data:
        repo_path = Path(repo_data["repo_path"])
        worktree_path = Path(repo_data["worktree_path"])
        config = initialization.load_par_config(repo_path)
        if config:
            # Run initialization but don't change tmux working directory
            initialization.run_initialization(
                config, session_name, worktree_path, workspace_mode=True
            )

    # Create workspace session data for global state
    # Workspaces are now stored as special sessions, not separate entities
    workspace_data = {
        "label": label,
        "repository_path": str(workspace_root),  # Use workspace root as "repository"
        "repository_name": f"workspace-{label}",
        "worktree_path": str(workspace_root),  # tmux session runs from workspace root
        "tmux_session_name": session_name,
        "branch_name": label,  # All repos get this branch name
        "created_at": datetime.datetime.utcnow().isoformat(),
        "session_type": "workspace",
        "workspace_repos": repos_data,  # Store repo info for workspace-specific operations
    }
    _add_workspace_session(workspace_data)

    typer.secho(
        f"Successfully started workspace '{label}' with {len(repos_data)} repositories.",
        fg="bright_green",
        bold=True,
    )
    for repo_data in repos_data:
        typer.echo(f"  {repo_data['repo_name']}: {repo_data['worktree_path']}")
    typer.echo(f"  Session: {session_name}")
    typer.echo(f"To open: par open {label}")  # Now works with global open command

    if open_session:
        open_workspace_session(label)


def list_workspace_sessions():
    """List all workspace sessions globally (now shown in main par ls)."""
    all_sessions = core._get_all_sessions()
    workspace_sessions = {k: v for k, v in all_sessions.items() if v.get("session_type") == "workspace"}

    if not workspace_sessions:
        typer.secho("No workspace sessions found.", fg="yellow")
        typer.echo("Workspaces are now shown in 'par ls' alongside regular sessions.")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold magenta", title="Workspace Sessions")
    table.add_column("Label", style="cyan", no_wrap=True)
    table.add_column("Repositories", style="green")
    table.add_column("Session", style="magenta", no_wrap=True)
    table.add_column("Created", style="dim")

    for label, data in workspace_sessions.items():
        repos_info = data.get("workspace_repos", [])
        repos = ", ".join([repo["repo_name"] for repo in repos_info])
        session_name = data["tmux_session_name"]
        created = data.get("created_at", "Unknown")
        if created != "Unknown":
            # Format datetime to be more readable
            try:
                dt = datetime.datetime.fromisoformat(created)
                created = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        table.add_row(label, repos, session_name, created)

    console.print(table)
    typer.echo("\nTip: Use 'par ls' to see all sessions including workspaces together.")


def open_workspace_session(label: str):
    """Open/attach to a workspace session (now handled by core.open_session)."""
    # Delegate to core.open_session since workspaces are now regular sessions
    core.open_session(label)


def remove_workspace_session(label: str):
    """Remove a workspace session (now handled by core.remove_session)."""
    # Delegate to core.remove_session since workspaces are now regular sessions
    core.remove_session(label)


def remove_all_workspace_sessions():
    """Remove all workspace sessions globally."""
    # Get all workspace sessions from global sessions
    all_sessions = core._get_all_sessions()
    workspace_sessions = {k: v for k, v in all_sessions.items() if v.get("session_type") == "workspace"}

    if not workspace_sessions:
        typer.secho("No workspace sessions to remove.", fg="yellow")
        return

    # Confirm removal
    labels = list(workspace_sessions.keys())
    typer.echo(f"This will remove {len(labels)} workspace sessions:")
    for label in labels:
        workspace_root = Path(workspace_sessions[label]["repository_path"]).name
        typer.echo(f"  - {label} ({workspace_root})")

    if not typer.confirm("Are you sure?"):
        typer.echo("Cancelled.")
        return

    # Remove each session
    for label in labels:
        try:
            remove_workspace_session(label)
        except typer.Exit:
            # Continue removing other sessions even if one fails
            pass

    typer.secho("All workspace sessions removed.", fg="green")


def open_workspace_in_ide(label: str, ide: str):
    """Open a workspace in the specified IDE."""
    # Get workspace session from global sessions
    session_data = core._get_session(label)

    if not session_data or session_data.get("session_type") != "workspace":
        typer.secho(f"Error: Workspace '{label}' not found.", fg="red", err=True)
        raise typer.Exit(1)

    repos_data = session_data["workspace_repos"]

    # Generate and save workspace file
    workspace_file = utils.save_vscode_workspace_file(label, repos_data)

    # Open in specified IDE
    try:
        if ide == "code":
            operations.run_cmd([ide, str(workspace_file)])
            typer.secho(f"Opening workspace '{label}' in VSCode...", fg="green")
        elif ide == "cursor":
            operations.run_cmd([ide, str(workspace_file)])
            typer.secho(f"Opening workspace '{label}' in Cursor...", fg="green")
        else:
            typer.secho(f"Error: Unsupported IDE '{ide}'", fg="red", err=True)
            raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Error opening {ide}: {e}", fg="red", err=True)
        typer.echo(f"Make sure {ide} is installed and in your PATH.")
        raise typer.Exit(1)
