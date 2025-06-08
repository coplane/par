# Par: Parallel Worktree & Session Manager

> **Easily manage parallel development workflows with isolated Git worktrees and tmux sessions**

`par` is a command-line tool designed to simplify parallel development within a single Git repository. It's specifically designed for working with AI coding assistants, background agents, or multiple development contexts simultaneously, `par` creates isolated workspaces that don't interfere with each other.

## Why Par?

Tools like OpenAI Codex, Claude Code, and other coding agents have made it easier to parallelize the work on multiple features, experiments, or problems simultaneously. However, traditional Git branch switching is not ideal for handling multiple concurrent workstreams on the same repository.

`par` solves this by creating **isolated development environments** for each task:

- **🔀 Git Worktrees**: Each session gets its own directory and branch
- **🖥️ Tmux Sessions**: Persistent terminal sessions where agents can run in the background
- **🏷️ Simple Labels**: Easy-to-remember names for each session
- **📡 Remote Control**: Send commands to any or all sessions
- **👁️ Overview Mode**: Monitor all sessions simultaneously
- **🏢 Multi-Repo Workspaces**: Unified development across multiple repositories
- **🎨 IDE Integration**: Native VSCode/Cursor workspace support with auto-generated configs

https://github.com/user-attachments/assets/88eb4aed-c00d-4238-b1a9-bcaa34c975c3



## Key Features

### 🚀 **Quick Start**
```bash
par start feature-auth    # Creates worktree, branch, and tmux session
par start bugfix-login    # Another isolated session
par start experiment-ai   # Yet another session
```

### 📋 **Session Management**
```bash
par ls                    # List all active sessions
par open feature-auth     # Switch to a specific session
par rm bugfix-login       # Clean up completed work
```

### 📡 **Remote Execution**  
```bash
par send feature-auth "pnpm test"           # Run tests in one session
par send all "git status"                  # Check status across all sessions
```

### 🎛️ **Control Center**
```bash
par control-center        # View all sessions in a tiled layout
```

### 🏢 **Multi-Repository Workspaces**
```bash
par workspace start feature-auth --repos frontend,backend
par workspace code feature-auth     # Open in VSCode with multi-repo support
par workspace open feature-auth     # Attach to unified tmux session
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

### Starting a New Session

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

### Managing Sessions

**List all sessions:**
```bash
par ls
```

**Open a session:**
```bash
par open my-feature
```

**Remove completed work:**
```bash
par rm my-feature      # Remove specific session
par rm all             # Remove all sessions (with confirmation)
```

> **Note**: When removing checkout sessions, `par` only removes the worktree and tmux session. It does not delete the original branch since it wasn't created by `par`.

### Remote Command Execution

**Send commands to specific sessions:**
```bash
par send my-feature "npm install"
par send backend-work "python manage.py migrate"
par send docs-update "mkdocs serve"
```

**Broadcast to all sessions:**
```bash
par send all "git status"
par send all "npm test"
```

### Control Center

View all sessions simultaneously in a tiled tmux layout:

```bash
par control-center
```

> **Note**: Must be run from outside tmux. Creates a new session and attaches to each session in its own pane.

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
      condition: "file_exists:frontend/.env.example"
      
    - name: "Install backend dependencies"
      command: "cd backend && uv sync"
      condition: "directory_exists:backend"
      
    # Simple string commands are also supported
    - "echo 'Workspace initialized!'"
```

**Supported condition types:**
- `directory_exists:path` - Check if directory exists
- `file_exists:path` - Check if file exists  
- `env:VAR_NAME` - Check if environment variable is set

When you run `par start my-feature`, these commands will automatically execute in the new session's tmux environment.

## Multi-Repository Workspaces

For projects spanning multiple repositories (like frontend/backend splits or microservices), `par` provides **workspace** functionality that manages multiple repositories together in a unified development environment.

### Why Workspaces?

When working on features that span multiple repositories, you typically need to:
- Create branches with the same name across repos
- Keep terminal sessions open for each repo
- Switch between repositories frequently
- Manage development servers for multiple services

Workspaces solve this by creating a single tmux session with dedicated panes for each repository, all sharing the same branch name.

### Quick Start

```bash
# Navigate to directory containing multiple repos
cd /path/to/my-project     # contains frontend/, backend/, docs/

# Start workspace with auto-detection
par workspace start feature-auth

# Or specify repositories explicitly
par workspace start feature-auth --repos frontend,backend

# Open in your preferred IDE with proper multi-repo support
par workspace code feature-auth     # VSCode
par workspace cursor feature-auth   # Cursor
```

### Workspace Commands

**Create a workspace:**
```bash
par workspace start <label> [--repos repo1,repo2] [--open]
```

**List workspaces:**
```bash
par workspace ls
```

**Open workspace:**
```bash
par workspace open <label>        # Attach to tmux session
par workspace code <label>        # Open in VSCode  
par workspace cursor <label>      # Open in Cursor
```

**Remove workspace:**
```bash
par workspace rm <label>          # Remove specific workspace
par workspace rm all              # Remove all workspaces
```

### How Workspaces Work

When you create a workspace, `par` automatically:

1. **Detects repositories** in the current directory (or uses `--repos`)
2. **Creates worktrees** for each repository with the same branch name
3. **Creates tmux session** with multiple panes (one per repository)  
4. **Generates IDE workspace files** for seamless editor integration

**Example directory structure:**
```
my-fullstack-app/
├── frontend/           # React app
├── backend/            # Python API  
└── docs/              # Documentation

# After: par workspace start user-auth
# Creates branches: user-auth in all three repos
# Creates tmux session with 3 panes
# Each pane starts in its respective worktree
```

### IDE Integration

Workspaces include first-class IDE support that solves the common problem of multi-repo development in editors.

**VSCode Integration:**
```bash
par workspace code user-auth
```

This generates and opens a `.code-workspace` file containing:
```json
{
  "folders": [
    {
      "name": "frontend (user-auth)",
      "path": "/path/to/worktrees/frontend/user-auth"
    },
    {
      "name": "backend (user-auth)", 
      "path": "/path/to/worktrees/backend/user-auth"
    }
  ],
  "settings": {
    "git.detectSubmodules": false,
    "git.repositoryScanMaxDepth": 1
  }
}
```

**Benefits:**
- Each repository appears as a separate folder in the explorer
- Git operations work correctly for each repository
- All repositories are on the correct feature branch
- No worktree plugin configuration needed

### Repository Specification

**Auto-detection (recommended):**
```bash
par workspace start feature-name
# Automatically finds all git repositories in current directory
```

**Explicit specification:**
```bash
par workspace start feature-name --repos frontend,backend,shared
# Only includes specified repositories
```

**Comma-separated syntax:**
```bash
--repos repo1,repo2,repo3
--repos "frontend, backend, docs"    # Spaces are trimmed
```

### Workspace Organization

Workspaces are organized separately from single-repo sessions:

```
~/.local/share/par/
├── worktrees/                  # Single-repo sessions
│   └── <repo-hash>/
└── workspaces/                 # Multi-repo workspaces
    └── <workspace-hash>/
        └── <workspace-label>/
            ├── frontend/
            │   └── feature-auth/     # Worktree
            ├── backend/
            │   └── feature-auth/     # Worktree  
            └── feature-auth.code-workspace
```

### Workspace Initialization

Workspaces support the same `.par.yaml` initialization as single repositories. Place the file in your workspace root directory:

```yaml
# .par.yaml in workspace root
initialization:
  commands:
    - name: "Install frontend dependencies"
      command: "pnpm install"
      working_directory: "frontend"
      
    - name: "Install backend dependencies"  
      command: "uv sync"
      working_directory: "backend"
      
    - name: "Start development servers"
      command: "npm run dev"
      working_directory: "frontend"
```

The `working_directory` field runs commands in specific subdirectories, perfect for multi-repo setups.

### Example Workflows

**Full-stack feature development:**
```bash
# 1. Start workspace for new feature
cd my-app/
par workspace start user-profiles --repos frontend,backend

# 2. Open in IDE with proper multi-repo support
par workspace code user-profiles

# 3. Work across repositories - each has user-profiles branch
# 4. Use tmux session for terminal work
par workspace open user-profiles

# 5. Clean up when feature is complete
par workspace rm user-profiles
```

**Microservices development:**
```bash
# Work on API changes affecting multiple services
par workspace start api-v2 --repos auth-service,user-service,gateway

# All services get api-v2 branch
# Single tmux session for monitoring all services
# IDE workspace shows all services together
```

### Branch Creation

Workspaces create branches from the **currently checked out branch** in each repository, not necessarily from `main`. This allows for:

- **Feature branches from develop**: If repos are on `develop`, workspace branches from `develop`
- **Different base branches**: Each repo can be on different branches before workspace creation
- **Flexible workflows**: Supports GitFlow, GitHub Flow, or custom branching strategies

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

