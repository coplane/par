"""Initialization support for .par.yaml configuration files."""

from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml
from rich.console import Console

from . import operations, utils


def load_par_config(repo_root: Path) -> Optional[Dict[str, Any]]:
    """Load .par.yaml configuration from repository root."""
    config_file = repo_root / ".par.yaml"
    if not config_file.exists():
        return None

    try:
        with open(config_file, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        typer.secho(f"Warning: Invalid .par.yaml file: {e}", fg="yellow")
        return None
    except Exception as e:
        typer.secho(f"Warning: Could not read .par.yaml: {e}", fg="yellow")
        return None


def run_initialization(
    config: Dict[str, Any],
    session_name: str,
    worktree_path: Path,
    workspace_mode: bool = False,
) -> None:
    """Run initialization commands from .par.yaml configuration."""
    initialization = config.get("initialization", {})
    commands = initialization.get("commands", [])

    if not commands:
        return

    console = Console()
    console.print(
        f"[cyan]Running initialization commands for session '{session_name}'...[/cyan]"
    )

    for i, command_config in enumerate(commands):
        if isinstance(command_config, str):
            # Simple string command
            command = command_config
            name = f"Command {i + 1}"
        elif isinstance(command_config, dict):
            # Structured command with name
            command = command_config.get("command")
            name = command_config.get("name", f"Command {i + 1}")

            if not command:
                typer.secho(
                    f"Warning: Skipping command {i + 1}: no 'command' specified",
                    fg="yellow",
                )
                continue
        else:
            typer.secho(
                f"Warning: Skipping invalid command config at index {i}", fg="yellow"
            )
            continue

        console.print(f"[green]Running:[/green] {name}")

        # Always cd to worktree root first to ensure consistent starting point
        full_command = f"cd {worktree_path} && {command}"

        # In workspace mode, show which repo we're running in
        if workspace_mode:
            console.print(f"[dim]  Repo: {worktree_path.name}[/dim]")

        console.print(f"[dim]  Command: {command}[/dim]")

        try:
            operations.send_tmux_keys(session_name, full_command)
        except Exception as e:
            typer.secho(f"Error running command '{name}': {e}", fg="red")
            # Continue with other commands even if one fails

    console.print(
        f"[green]✅ Initialization complete for session '{session_name}'[/green]"
    )


def show_welcome_message(workspace_mode: bool = False) -> None:
    """Display welcome message with ASCII art, current contexts, and suggested next steps."""
    from rich.table import Table

    console = Console()

    # ASCII Art
    ascii_art = """
    ____  ___    ____
   / __ \\/   |  / __ \\
  / /_/ / /| | / /_/ /
 / ____/ ___ |/ _, _/ 
/_/   /_/  |_/_/ |_|   
"""

    console.print(f"[bold blue]{ascii_art}[/bold blue]")
    console.print("[bold magenta]parallel worktree & session manager[/bold magenta]")
    console.print()

    try:
        # Get context information
        contexts_info = _get_smart_contexts()

        if contexts_info["total_contexts"] > 0:
            if contexts_info["is_inside_workspace"]:
                # Show current workspace info
                current_workspace = contexts_info["current_workspace"]
                console.print(
                    f"🌟 [bold green]Active Workspace:[/bold green] [cyan]{current_workspace['label']}[/cyan]"
                )
                console.print()

                # Create table for workspace repos
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Repository", style="green")
                table.add_column("Branch", style="yellow")

                for repo in current_workspace["repos"]:
                    table.add_row(repo["name"], repo["branch"])

                console.print(table)

                # Show workspace commands since we're inside one
                console.print()
                console.print("⚡ [bold yellow]Workspace Commands:[/bold yellow]")
                console.print(
                    "  [bright_blue]par code[/bright_blue]             # Open in VSCode"
                )
                console.print(
                    "  [bright_blue]par cursor[/bright_blue]           # Open in Cursor"
                )
            else:
                # Show all contexts (ls-style)
                console.print(
                    f"🌟 [bold green]Development Contexts[/bold green] ({contexts_info['total_contexts']} active)"
                )
                console.print()

                # Create table for all contexts
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Label", style="cyan")
                table.add_column("Type", style="blue")
                table.add_column("Repositories", style="green")
                table.add_column("Branch", style="yellow")

                for context in contexts_info["contexts"]:
                    repos_display = ", ".join(context["repos"])
                    table.add_row(
                        context["label"],
                        context["type"].capitalize(),
                        repos_display,
                        context["branch"],
                    )

                console.print(table)
                console.print()
                console.print(
                    "[dim]Run [cyan]par --help[/cyan] to see all available commands[/dim]"
                )
        else:
            console.print("🌟 [bold green]Ready to Start![/bold green]")
            console.print()
            console.print("[dim]No active development contexts found[/dim]")
            console.print(
                "[dim]Create one with: [cyan]par start <name>[/cyan] or [cyan]par ws start <name>[/cyan][/dim]"
            )
            console.print()
            console.print(
                "[dim]Run [cyan]par --help[/cyan] to see all available commands[/dim]"
            )

    except Exception:
        # Fallback if context detection fails
        console.print("🌟 [bold green]Ready to Start![/bold green]")
        console.print()
        console.print(
            "[dim]Run [cyan]par --help[/cyan] to see all available commands[/dim]"
        )


def _get_smart_contexts() -> Dict[str, Any]:
    """Get context information with smart detection of current location."""
    try:
        import json
        from pathlib import Path

        current_dir = Path.cwd()
        current_path_str = str(current_dir.resolve())

        # Check if we're inside a workspace
        state_file = utils.get_data_dir() / "workspaces.json"
        current_workspace = None
        is_inside_workspace = False

        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    all_workspaces = json.loads(f.read().strip() or "{}")

                # Check if current directory is within any workspace
                for workspace_root, workspace_data in all_workspaces.items():
                    for ws_label, ws_info in workspace_data.items():
                        # Check if we're in any of the workspace's repo paths
                        for repo_data in ws_info.get("repos", []):
                            worktree_path = repo_data.get("worktree_path", "")
                            if worktree_path and current_path_str.startswith(
                                str(Path(worktree_path).parent.parent)
                            ):
                                is_inside_workspace = True
                                current_workspace = {
                                    "label": ws_label,
                                    "repos": [
                                        {
                                            "name": r["repo_name"],
                                            "branch": r["branch_name"],
                                        }
                                        for r in ws_info.get("repos", [])
                                    ],
                                }
                                break
                        if is_inside_workspace:
                            break
                    if is_inside_workspace:
                        break
            except Exception:
                pass

        if is_inside_workspace and current_workspace:
            return {
                "total_contexts": 1,
                "is_inside_workspace": True,
                "current_workspace": current_workspace,
                "contexts": [],
            }
        else:
            # Get all contexts for ls-style display
            workspace_contexts = _get_workspace_contexts()
            session_contexts = _get_session_contexts()

            all_contexts = workspace_contexts["contexts"] + session_contexts["contexts"]

            return {
                "total_contexts": len(all_contexts),
                "is_inside_workspace": False,
                "current_workspace": None,
                "contexts": all_contexts,
            }

    except Exception:
        return {
            "total_contexts": 0,
            "is_inside_workspace": False,
            "current_workspace": None,
            "contexts": [],
        }


def _get_session_contexts() -> Dict[str, Any]:
    """Get information about current single-repo sessions."""
    try:
        import subprocess

        from . import core

        # Check if we're in a git repository first (silently)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_repo_root = Path(result.stdout.strip())
            current_repo_name = current_repo_root.name
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Not in a git repository, can't get sessions
            return {"total_contexts": 0, "contexts": []}

        sessions = core._get_repo_sessions()
        contexts = []
        for label, data in sessions.items():
            contexts.append(
                {
                    "label": label,
                    "type": "session",
                    "repos": [current_repo_name],
                    "branch": data["branch_name"],
                }
            )

        return {"total_contexts": len(contexts), "contexts": contexts}
    except Exception:
        return {"total_contexts": 0, "contexts": []}


def _get_workspace_contexts() -> Dict[str, Any]:
    """Get information about workspace contexts only."""
    try:
        import subprocess
        from pathlib import Path

        contexts = []
        current_repo_name = None
        current_dir = Path.cwd()

        # Try to get current repo name if we're in a git repository (silently)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_repo_root = Path(result.stdout.strip())
            current_repo_name = current_repo_root.name
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Not in a git repository
            pass

        # Check all possible workspace locations
        state_file = utils.get_data_dir() / "workspaces.json"
        if state_file.exists():
            try:
                import json

                with open(state_file, "r") as f:
                    all_workspaces = json.loads(f.read().strip() or "{}")

                # Check if current directory is within any workspace
                current_path_str = str(current_dir.resolve())

                for workspace_root, workspace_data in all_workspaces.items():
                    for ws_label, ws_info in workspace_data.items():
                        # Check if we're inside this workspace's directory structure
                        workspace_in_scope = False

                        # Check if current directory matches workspace root
                        if current_path_str == workspace_root:
                            workspace_in_scope = True

                        # Check if we're in any of the workspace's repo paths
                        for repo_data in ws_info.get("repos", []):
                            worktree_path = repo_data.get("worktree_path", "")
                            if worktree_path and current_path_str.startswith(
                                str(Path(worktree_path).parent)
                            ):
                                workspace_in_scope = True
                                break

                        # Check if current repo is part of this workspace
                        if current_repo_name:
                            for repo_data in ws_info.get("repos", []):
                                if repo_data.get("repo_name") == current_repo_name:
                                    workspace_in_scope = True
                                    break

                        if workspace_in_scope:
                            repo_names = [
                                r["repo_name"] for r in ws_info.get("repos", [])
                            ]
                            first_repo = ws_info.get("repos", [{}])[0]
                            contexts.append(
                                {
                                    "label": ws_label,
                                    "type": "workspace",
                                    "repos": repo_names,
                                    "branch": first_repo.get("branch_name", "unknown"),
                                }
                            )
            except Exception:
                pass

        return {"total_contexts": len(contexts), "contexts": contexts}
    except Exception:
        return {"total_contexts": 0, "contexts": []}
