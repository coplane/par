"""Workspace branch renaming functionality."""

from pathlib import Path
from typing import Dict, Any, Optional

import typer
from rich.console import Console

from . import operations
from .state_manager import get_workspace_state_manager


def rename_repo_branch(repo_name: str, new_branch: str) -> None:
    """Rename a repository's branch within the current workspace."""
    console = Console()
    
    # Find current workspace
    current_workspace = _find_current_workspace()
    if not current_workspace:
        typer.secho("Error: Not currently in a workspace.", fg="red", err=True)
        typer.secho("The 'par rename' command only works within workspaces.", fg="red", err=True)
        raise typer.Exit(1)
    
    workspace_label, workspace_data = current_workspace
    
    # Find the repository in the workspace
    repo_data = None
    for repo in workspace_data["repos"]:
        if repo["repo_name"] == repo_name:
            repo_data = repo
            break
    
    if not repo_data:
        available_repos = [r["repo_name"] for r in workspace_data["repos"]]
        typer.secho(f"Error: Repository '{repo_name}' not found in workspace '{workspace_label}'.", fg="red", err=True)
        typer.secho(f"Available repositories: {', '.join(available_repos)}", fg="yellow")
        raise typer.Exit(1)
    
    worktree_path = Path(repo_data["worktree_path"])
    old_branch = repo_data["branch_name"]
    
    if not worktree_path.exists():
        typer.secho(f"Error: Worktree path '{worktree_path}' does not exist.", fg="red", err=True)
        raise typer.Exit(1)
    
    console.print(f"[cyan]Renaming branch for repository '[bold]{repo_name}[/bold]'[/cyan]")
    console.print(f"  From: [yellow]{old_branch}[/yellow]")
    console.print(f"  To:   [green]{new_branch}[/green]")
    console.print()
    
    # Rename the git branch
    try:
        # First, make sure we're on the branch we want to rename
        operations.run_cmd(["git", "checkout", old_branch], cwd=worktree_path)
        
        # Rename the branch
        operations.run_cmd(["git", "branch", "-m", new_branch], cwd=worktree_path)
        
        # Update upstream tracking if it exists
        try:
            # Check if there's an upstream branch
            result = operations.run_cmd(
                ["git", "rev-parse", "--abbrev-ref", f"{old_branch}@{{upstream}}"],
                cwd=worktree_path,
                suppress_output=True
            )
            if result.returncode == 0:
                # There is an upstream, update it
                upstream = result.stdout.strip()
                remote_name = upstream.split('/')[0] if '/' in upstream else 'origin'
                operations.run_cmd(
                    ["git", "push", remote_name, f":{old_branch}"],  # Delete old remote branch
                    cwd=worktree_path,
                    suppress_output=True
                )
                operations.run_cmd(
                    ["git", "push", "-u", remote_name, new_branch],  # Push new branch
                    cwd=worktree_path,
                    suppress_output=True
                )
        except Exception:
            # No upstream or couldn't update it, that's okay
            pass
        
        console.print(f"[green]✅ Successfully renamed git branch[/green]")
        
    except Exception as e:
        typer.secho(f"Error renaming git branch: {e}", fg="red", err=True)
        raise typer.Exit(1)
    
    # Update Par's workspace state
    try:
        _update_workspace_state(workspace_label, workspace_data, repo_name, new_branch)
        console.print(f"[green]✅ Updated Par workspace state[/green]")
        
    except Exception as e:
        typer.secho(f"Error updating workspace state: {e}", fg="red", err=True)
        typer.secho("The git branch was renamed, but Par's state may be inconsistent.", fg="yellow")
        raise typer.Exit(1)
    
    console.print()
    console.print(f"[bold green]Branch rename complete![/bold green]")
    console.print(f"Repository '[cyan]{repo_name}[/cyan]' is now on branch '[green]{new_branch}[/green]'")


def _find_current_workspace() -> Optional[tuple[str, Dict[str, Any]]]:
    """Find the current workspace based on the current directory."""
    current_dir = Path.cwd()
    current_path_str = str(current_dir.resolve())
    
    state_manager = get_workspace_state_manager()
    
    try:
        all_workspaces = state_manager.load()
        
        # Check if current directory is within any workspace
        for workspace_root, workspace_data in all_workspaces.items():
            for ws_label, ws_info in workspace_data.items():
                # Check if we're in any of the workspace's repo paths
                for repo_data in ws_info.get("repos", []):
                    worktree_path = repo_data.get("worktree_path", "")
                    if worktree_path and current_path_str.startswith(str(Path(worktree_path).parent.parent)):
                        return ws_label, ws_info
        
        return None
        
    except Exception:
        return None


def _update_workspace_state(workspace_label: str, workspace_data: Dict[str, Any], repo_name: str, new_branch: str) -> None:
    """Update the workspace state with the new branch name."""
    state_manager = get_workspace_state_manager()
    all_workspaces = state_manager.load()
    
    # Find and update the specific repo's branch name
    workspace_root = workspace_data["workspace_root"]
    for repo_data in all_workspaces[workspace_root][workspace_label]["repos"]:
        if repo_data["repo_name"] == repo_name:
            repo_data["branch_name"] = new_branch
            break
    
    # Save updated state
    state_manager.save(all_workspaces)