# Par: Parallel Worktree & Session Manager

> **Easily manage parallel development workflows with isolated Git worktrees and tmux sessions**

`par` is a command-line tool designed to simplify parallel development within a single Git repository. It's specifically designed for working with AI coding assistants, background agents, or multiple development contexts simultaneously, `par` creates isolated workspaces that don't interfere with each other.

## Why Par?

Tools like OpenAI Codex, Claude Code, and other coding agents have made it easier to parallelize the work on multiple features, experiments, or problems simultaneously. However, traditional Git branch switching is not ideal for handling multiple concurrent workstreams on the same repository.

`par` solves this by creating **isolated development environments** for each task:

- **🔀 Git Worktrees**: Each workspace gets its own directory and branch
- **🖥️ Tmux Sessions**: Persistent terminal sessions where agents can run in the background
- **🏷️ Simple Labels**: Easy-to-remember names for each workspace
- **📡 Remote Control**: Send commands to any or all sessions
- **👁️ Overview Mode**: Monitor all workspaces simultaneously

https://github.com/user-attachments/assets/88eb4aed-c00d-4238-b1a9-bcaa34c975c3

## Key Features

### 🚀 **Quick Start**

```bash
par start feature-auth    # Creates worktree, branch, and tmux session
par start bugfix-login    # Another isolated workspace
par start experiment-ai   # Yet another workspace
```

### 📋 **Session Management**

```bash
par ls                    # List all active workspaces
par open feature-auth     # Switch to a specific workspace
par rm bugfix-login       # Clean up completed work
```

### 📡 **Remote Execution**

```bash
par send feature-auth "pnpm test"           # Run tests in one workspace
par send all "git status"                  # Check status across all workspaces
```

### 🎛️ **Control Center**

```bash
par control-center        # View all sessions in a tiled layout
```

## Installation

### Prerequisites

- **Git** - Version control system
- **tmux** - Terminal multiplexer
- **Python 3.12+** - Runtime environment
- **uv** - Package manager (recommended)

### Install from Source

```bash
git clone https://github.com/coplane/par.git
cd par
uv tool install .
```

### Verify Installation

```bash
par --version
par --help
```

## Usage

### Starting a New Workspace

Create a new isolated development environment:

```bash
cd /path/to/your/git/repo
par start my-feature
```

This creates:

- Git worktree at `~/.local/share/par/worktrees/<repo-hash>/my-feature/`
- Git branch named `my-feature`
- tmux session named `par-<repo>-<hash>-my-feature`

### Checking Out Existing Branches and PRs

Work with existing branches or review PRs without creating new branches:

```bash
# Checkout existing branch
par checkout existing-branch

# Checkout PR by number
par checkout pr/123

# Checkout PR by URL
par checkout https://github.com/owner/repo/pull/456

# Checkout remote branch from fork
par checkout alice:feature-branch

# Checkout with custom session label
par checkout develop --label dev-work
```

**Supported formats:**

- `branch-name` - Local or origin branch
- `pr/123` - GitHub PR by number
- `https://github.com/owner/repo/pull/123` - GitHub PR by URL
- `username:branch` - Remote branch from fork
- `remote/branch` - Branch from specific remote

### Managing Workspaces

**List all workspaces:**

```bash
par ls
```

**Open a workspace:**

```bash
par open my-feature
```

**Remove completed work:**

```bash
par rm my-feature      # Remove specific workspace
par rm all             # Remove all workspaces (with confirmation)
```

> **Note**: When removing checkout sessions, `par` only removes the worktree and tmux session. It does not delete the original branch since it wasn't created by `par`.

### Remote Command Execution

**Send commands to specific workspaces:**

```bash
par send my-feature "npm install"
par send backend-work "python manage.py migrate"
par send docs-update "mkdocs serve"
```

**Broadcast to all workspaces:**

```bash
par send all "git status"
par send all "npm test"
```

### Control Center

View all workspaces simultaneously in a tiled tmux layout:

```bash
par control-center
```

> **Note**: Must be run from outside tmux. Creates a new session and attaches to each workspace in its own pane.

### Automatic Initialization with .par.yaml

`par` can automatically run initialization commands when creating new worktrees. Simply add a `.par.yaml` file to your repository root:

```yaml
# .par.yaml
initialization:
  commands:
    - name: "Install frontend dependencies"
      command: "cd frontend && pnpm install"

    - name: "Setup environment file"
      command: "cd frontend && cp .env.example .env"

    - name: "Install backend dependencies"
      command: "cd backend && uv sync"

    # Simple string commands are also supported
    - "echo 'Workspace initialized!'"
```

When you run `par start my-feature`, these commands will automatically execute in the new worktree's tmux session.

## Advanced Usage

### Repository-Scoped Sessions

`par` automatically scopes sessions to the current Git repository. You can use the same labels across different projects without conflicts:

```bash
cd ~/project-a
par start feature-auth    # Creates project-a/feature-auth

cd ~/project-b
par start feature-auth    # Creates separate project-b/feature-auth
```

## Configuration

### Data Directory

Par stores its data in `~/.local/share/par/` (or `$XDG_DATA_HOME/par/`):

```
~/.local/share/par/
├── state.json              # Session metadata
└── worktrees/              # Git worktrees organized by repo
    └── <repo-hash>/
        ├── feature-1/      # Individual workspaces
        ├── feature-2/
        └── experiment-1/
```

### Session Naming Convention

tmux sessions follow the pattern: `par-<repo-name>-<repo-hash>-<label>`

Example: `par-myproject-a1b2c3d4-feature-auth`

### Cleaning Up

Remove all par-managed resources for the current repository:

```bash
par rm all
```

Remove specific stale sessions:

```bash
par rm old-feature-name
```
