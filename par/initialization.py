"""Initialization support for .par.yaml configuration files."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def run_initialization(config: Dict[str, Any], session_name: str) -> None:
    """Run initialization commands from .par.yaml configuration."""
    initialization = config.get("initialization", {})
    commands = initialization.get("commands", [])
    
    if not commands:
        return

    console = Console()
    console.print(f"[cyan]Running initialization commands for session '{session_name}'...[/cyan]")

    for i, command_config in enumerate(commands):
        if isinstance(command_config, str):
            # Simple string command
            command = command_config
            name = f"Command {i + 1}"
        elif isinstance(command_config, dict):
            # Structured command with name and optional condition
            command = command_config.get("command")
            name = command_config.get("name", f"Command {i + 1}")
            condition = command_config.get("condition")
            
            if not command:
                typer.secho(f"Warning: Skipping command {i + 1}: no 'command' specified", fg="yellow")
                continue
                
            # Check condition if specified
            if condition and not _check_condition(condition):
                console.print(f"[dim]Skipping '{name}': condition '{condition}' not met[/dim]")
                continue
        else:
            typer.secho(f"Warning: Skipping invalid command config at index {i}", fg="yellow")
            continue

        console.print(f"[green]Running:[/green] {name}")
        console.print(f"[dim]  Command: {command}[/dim]")
        
        try:
            operations.send_tmux_keys(session_name, command)
        except Exception as e:
            typer.secho(f"Error running command '{name}': {e}", fg="red")
            # Continue with other commands even if one fails

    console.print(f"[green]✅ Initialization complete for session '{session_name}'[/green]")


def _check_condition(condition: str) -> bool:
    """Check if a condition is met. Returns True if condition passes."""
    if condition.startswith("directory_exists:"):
        directory = condition.split(":", 1)[1]
        return Path(directory).is_dir()
    elif condition.startswith("file_exists:"):
        file_path = condition.split(":", 1)[1]
        return Path(file_path).is_file()
    elif condition.startswith("env:"):
        env_var = condition.split(":", 1)[1]
        return os.getenv(env_var) is not None
    else:
        typer.secho(f"Warning: Unknown condition type: {condition}", fg="yellow")
        return True  # Default to running the command if condition is unknown