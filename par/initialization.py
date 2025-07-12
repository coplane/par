"""Initialization support for .par.yaml configuration files."""

import glob
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import typer
import yaml
from rich.console import Console

from . import operations


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


def copy_included_files(
    config: Dict[str, Any], repo_root: Path, worktree_path: Path
) -> None:
    """Copy files listed in the initialization.include section."""
    initialization = config.get("initialization", {})
    includes: Iterable[str] = initialization.get("include", [])
    for pattern in includes:
        # Expand pattern relative to the repository root
        full_pattern = str(repo_root / pattern)
        for src in glob.glob(full_pattern):
            src_path = Path(src)
            try:
                relative = src_path.relative_to(repo_root)
            except ValueError:
                # Skip paths outside the repository
                continue
            dest = worktree_path / relative
            if src_path.is_dir():
                shutil.copytree(src_path, dest, dirs_exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest)

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
