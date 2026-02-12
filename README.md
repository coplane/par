# Par: Parallel Worktree & Session Manager

> **Easily manage parallel development workflows with isolated Git worktrees and tmux sessions**

`par` is a **global** command-line tool designed to simplify parallel development across any Git repositories on your system. It's specifically designed for working with AI coding assistants, background agents, or multiple development contexts simultaneously, `par` creates isolated workspaces that don't interfere with each other.

## Why Par?

Tools like OpenAI Codex, Claude Code, and other coding agents have made it easier to parallelize the work on multiple features, experiments, or problems simultaneously. However, traditional Git branch switching is not ideal for handling multiple concurrent workstreams on the same repository.

`par` solves this by creating **isolated development environments** for each task:

- **🔀 Git Worktrees**: Each session gets its own directory and branch
- **🖥️ Tmux Sessions**: Persistent terminal sessions where agents can run in the background
- **🏷️ Globally Unique Labels**: Easy-to-remember names that work across all repositories
- **🌍 Global Management**: Create, list, and manage sessions from anywhere on your system
- **📡 Remote Control**: Send commands to any or all sessions globally
- **👁️ Overview Mode**: Monitor all sessions simultaneously
- **🏢 Multi-Repo Workspaces**: Unified development across multiple repositories
- **🎨 IDE Integration**: Native VSCode/Cursor workspace support with auto-generated configs

https://github.com/user-attachments/assets/88eb4aed-c00d-4238-b1a9-bcaa34c975c3

## Key Features

### 🚀 **Quick Start**

```bash
# From within a git repository
par start feature-auth    # Creates worktree, branch, and tmux session
par start feature-auth --base develop

# From anywhere on your system
par start bugfix-login --path /path/to/repo
par start experiment-ai --path ~/projects/my-app
```

### 📋 **Global Development Context Management**

```bash
par ls                    # List ALL sessions and workspaces globally
par open feature-auth     # Switch to any session or workspace from anywhere
par rm bugfix-login       # Clean up completed work globally
```

### 📡 **Global Remote Execution**

```bash
par send feature-auth "pnpm test"           # Run tests in one session
par send all "git status"                  # Check status across ALL sessions globally
```

### 🎛️ **Global Control Center**

```bash
par control-center        # View ALL sessions and workspaces globally with separate windows
```

### 🏢 **Multi-Repository Workspaces**

```bash
par workspace start feature-auth --repos frontend,backend
par workspace code feature-auth     # Open in VSCode with multi-repo support
par workspace open feature-auth     # Attach to unified tmux session
```

## Unified Development Context System

`par` provides a **unified interface** for managing both single-repository sessions and multi-repository workspaces. Whether you're working on a single feature branch or coordinating changes across multiple repositories, all your development contexts appear in one place.

### Two Development Modes:

- **Sessions**: Single-repo development with isolated branches (`par start`, `par checkout`)
- **Workspaces**: Multi-repo development with synchronized branches (`par workspace start`)

### Unified Commands:

- `par ls` - See all your development contexts (sessions + workspaces) in one table
- `par open <label>` - Switch to any session or workspace
- `par control-center` - View all contexts in separate tmux windows
- Tab completion works across both sessions and workspaces

This eliminates the need to remember which type of development context you're working with - just use the label and `par` handles the rest!

## Installation

### Prerequisites

- **Git** - Version control system
- **tmux** - Terminal multiplexer
- **Python 3.12+** - Runtime environment
- **uv** - Package manager (recommended)

### Install with uv

```bash
uv tool install par-cli
```

### Install with pip

```bash
pip install par-cli
```

### Install from Source

```bash
git clone https://github.com/coplane/par.git
cd par
uv tool install .
```

### Upgrade with uv

```bash
uv tool upgrade par-cli
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
# From within a git repository
par start my-feature
par start my-feature --base develop

# From anywhere, specifying the repository path
par start my-feature --path /path/to/your/git/repo
par start my-feature -p ~/projects/my-app
```

By default, `par start` branches from the current `HEAD` commit. Use `--base` to branch from a specific branch/reference. `par` resolves the base to a commit SHA, so uncommitted changes in your current worktree do not affect the new branch.

If the label already matches an existing local branch, `par start <label>` will reuse that branch and create a worktree with it checked out instead of creating a new branch.
If no local branch exists but `origin/<label>` exists, `par` fetches it and creates the worktree from `origin/<label>`.

This creates:

- Git worktree at `~/.local/share/par/worktrees/<repo-hash>/my-feature/`
- Git branch named `my-feature`
- tmux session named `par-<repo>-<hash>-my-feature`
- **Globally unique session** accessible from anywhere

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

# Checkout from anywhere specifying repository path
par checkout feature-branch --path /path/to/repo
par checkout pr/123 --path ~/projects/my-app --label pr-review
```

**Supported formats:**

- `branch-name` - Local or origin branch
- `pr/123` - GitHub PR by number
- `https://github.com/owner/repo/pull/123` - GitHub PR by URL
- `username:branch` - Remote branch from fork
- `remote/branch` - Branch from specific remote

### Global Development Context Management

**List all sessions and workspaces globally:**

```bash
par ls    # Shows ALL sessions and workspaces from anywhere
```

Shows all development contexts across all repositories in a unified table:

```
Par Development Contexts (Global)

┌────────────────┬───────────┬──────────────────┬──────────────┬─────────────────┬────────────┐
│ Label          │ Type      │ Repository/Work… │ Tmux Session │ Branch          │ Created    │
├────────────────┼───────────┼──────────────────┼──────────────┼─────────────────┼────────────┤
│ feature-auth   │ Session   │ my-app (proj…)   │ par-myapp-…  │ feature-auth    │ 2025-07-19 │
│ fullstack      │ Workspace │ workspace (2 re… │ par-ws-full… │ fullstack       │ 2025-07-19 │
│ bugfix-123     │ Checkout  │ other-repo (c…)  │ par-other-…  │ hotfix/bug-123  │ 2025-07-19 │
└────────────────┴───────────┴──────────────────┴──────────────┴─────────────────┴────────────┘
```

**Open any development context from anywhere:**

```bash
par open my-feature        # Opens session
par open fullstack-auth    # Opens workspace
```

**Remove completed work from anywhere:**

```bash
par rm my-feature      # Remove specific session/workspace globally
par rm all             # Remove ALL sessions and workspaces (with confirmation)
```

> **Note**: When removing checkout sessions, `par` only removes the worktree and tmux session. It does not delete the original branch since it wasn't created by `par`.

### Global Remote Command Execution

**Send commands to specific sessions :**

```bash
par send my-feature "npm install"
par send backend-work "python manage.py migrate"
par send workspace-name "git status"    # Works for workspaces too
```

**Broadcast to ALL sessions and workspaces globally:**

```bash
par send all "git status"    # Sends to every session everywhere
par send all "npm test"      # Runs tests across all contexts
```

### Global Control Center

View ALL development contexts simultaneously with dedicated tmux windows:

```bash
par control-center    # Works from anywhere, shows everything
```

Creates a unified `control-center` tmux session with separate windows for each development context (sessions and workspace repositories), giving you easy navigation across your entire development workflow.

> **Note**: Must be run from outside tmux. Creates a global control center session with dedicated windows for each context.

**Benefits of the windowed approach:**

- **Easy Navigation**: Use tmux window switching (`Ctrl-b + number` or `Ctrl-b + n/p`) to jump between contexts
- **Clean Organization**: Each development context gets its own dedicated window with a descriptive name
- **Scalable**: Works well with many sessions/workspaces (unlike tiled panes that become cramped)
- **Workspace Support**: For multi-repo workspaces, each repository gets its own window

### Automatic Initialization with .par.yaml

`par` can automatically run initialization commands when creating new worktrees. Simply add a `.par.yaml` file to your repository root:

```yaml
# .par.yaml
initialization:
  include:
    - .env
    - config/*.json
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

Files listed under `include` are copied from the repository root into each new worktree before any commands run. This lets you keep gitignored files like `.env` in the new environment.

All commands start from the worktree root directory. Use `cd <directory> &&` to run commands in subdirectories.

When you run `par start my-feature`, these commands will automatically execute in the new session's tmux environment.

## Multi-Repository Workspaces

For projects spanning multiple repositories (like frontend/backend splits or microservices), `par` provides **workspace** functionality that creates a single session managing multiple repositories together in a unified development environment.

### Why Workspaces?

When working on features that span multiple repositories, you typically need to:

- Create branches with the same name across repos
- Keep terminal sessions open for each repo
- Switch between repositories frequently
- Manage development servers for multiple services

Workspaces solve this by creating a **single global session** that starts from a unified workspace directory with access to all repositories, all sharing the same branch name.

### Quick Start

```bash
# From a directory containing multiple repos (auto-detection)
cd /path/to/my-project     # contains frontend/, backend/, docs/
par workspace start feature-auth

# From anywhere, specifying repositories by absolute path
par workspace start feature-auth --repos /path/to/frontend,/path/to/backend
par workspace start feature-auth --path /workspace/root --repos frontend,backend

# Open in your preferred IDE with proper multi-repo support
par workspace code feature-auth     # VSCode
par workspace cursor feature-auth   # Cursor
```

### Workspace Commands

**Create a workspace:**

```bash
par workspace start <label> [--path /workspace/root] [--repos repo1,repo2] [--open]
```

**List workspaces (now unified with sessions):**

```bash
par ls                            # Shows workspaces alongside sessions
par workspace ls                  # Shows only workspaces (deprecated)
```

**Open workspace (now unified):**

```bash
par open <label>                  # Opens workspace session
par workspace code <label>        # Open in VSCode
par workspace cursor <label>      # Open in Cursor
```

**Remove workspace (now unified):**

```bash
par rm <label>                    # Remove workspace
par workspace rm <label>          # Also works (delegates to global rm)
```

### How Workspaces Work

When you create a workspace, `par` automatically:

1. **Detects repositories** in the workspace directory (or uses `--repos` with absolute paths)
2. **Creates worktrees** for each repository with the same branch name
3. **Creates single global session** starting from unified workspace root with access to all repositories
4. **Generates IDE workspace files** for seamless editor integration
5. **Integrates with global par commands** - use `par ls`, `par open`, `par rm` etc.

**Example directory structure:**

```
# Original repositories anywhere on system:
my-fullstack-app/
├── frontend/           # React app
├── backend/            # Python API
└── docs/              # Documentation

# After: par workspace start user-auth --repos /home/user/projects/frontend,/home/user/projects/backend,/opt/company/docs
# Creates unified workspace at: ~/.local/share/par/workspaces/.../user-auth/
├── frontend/
├── backend/
├── docs/
└── user-auth.code-workspace

# Single tmux session starts from workspace root
# Navigate with: cd frontend/, cd backend/, cd docs/
# Global session accessible via: par open user-auth
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

Workspaces support the same `.par.yaml` initialization as single repositories. When you create a workspace, `par` runs the initialization commands from each repository's `.par.yaml` file in their respective worktrees.

For example, if both `frontend` and `backend` repositories have their own `.par.yaml` files:

```yaml
# frontend/.par.yaml
initialization:
  commands:
    - name: "Install dependencies"
      command: "pnpm install"
    - name: "Setup environment"
      command: "cp .env.example .env"

# backend/.par.yaml
initialization:
  commands:
    - name: "Install dependencies"
      command: "uv sync"
    - name: "Run migrations"
      command: "python manage.py migrate"
```

Each repository's initialization runs in its own worktree, ensuring proper isolation and consistent behavior.

### Example Workflows

**Full-stack feature development:**

```bash
# 1. Start workspace for new feature
par workspace start user-profiles --repos /path/to/frontend,/path/to/backend

# 2. Open in IDE with proper multi-repo support
par workspace code user-profiles

# 3. Open unified session
par open user-profiles

# 4. Work across repositories from single terminal
cd frontend/    # Switch to frontend worktree
cd ../backend/  # Switch to backend worktree
claude          # Run Claude from workspace root to see all repos

# 5. Global management
par ls                           # See all sessions including workspaces
par send user-profiles "git status"  # Send commands globally

# 6. Clean up when feature is complete
par rm user-profiles
```

**Microservices development:**

```bash
# Work on API changes affecting multiple services
par workspace start api-v2 --repos /srv/auth-service,/srv/user-service,/srv/gateway

# All services get api-v2 branch
# Single global session accessible from anywhere
# IDE workspace shows all services together
# Navigate: cd auth-service/, cd user-service/, etc.
# Global commands: par send api-v2 "docker-compose up"
```

### Branch Creation

Workspaces create branches from the **currently checked out branch** in each repository, not necessarily from `main`. This allows for:

- **Feature branches from develop**: If repos are on `develop`, workspace branches from `develop`
- **Different base branches**: Each repo can be on different branches before workspace creation
- **Flexible workflows**: Supports GitFlow, GitHub Flow, or custom branching strategies

## Advanced Usage

### Globally Unique Sessions

`par` enforces globally unique session labels across all repositories. This ensures you can manage sessions from anywhere without conflicts:

```bash
# All sessions must have unique labels globally
par start feature-auth --path ~/project-a    # Creates feature-auth session
par start feature-auth --path ~/project-b    # ❌ Error: label already exists
par start feature-auth-v2 --path ~/project-b # ✅ Works with unique label

# Access any session from anywhere
par open feature-auth      # Works from any directory
par ls                     # Shows all sessions globally
```

## Configuration

### Data Directory

Par stores its data in `~/.local/share/par/` (or `$XDG_DATA_HOME/par/`):

```
~/.local/share/par/
├── global_state.json       # Global session and workspace metadata
├── worktrees/              # Single-repo sessions organized by repo hash
│   └── <repo-hash>/
│       ├── feature-1/      # Individual worktrees
│       ├── feature-2/
│       └── experiment-1/
└── workspaces/             # Multi-repo workspaces
    └── <workspace-hash>/
        └── <workspace-label>/
            ├── frontend/
            │   └── feature-auth/     # Worktree
            ├── backend/
            │   └── feature-auth/     # Worktree
            └── feature-auth.code-workspace
```

### Session Naming Convention

tmux sessions follow the pattern: `par-<repo-name>-<repo-hash>-<label>`

Example: `par-myproject-a1b2c3d4-feature-auth`

### Cleaning Up

Remove all par-managed resources globally:

```bash
par rm all    # Removes ALL sessions and workspaces everywhere
```

Remove specific stale sessions:

```bash
par rm old-feature-name
```
