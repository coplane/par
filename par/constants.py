"""Configuration constants for Par."""


class SessionStatus:
    """Status values for Par sessions and workspaces"""

    CREATING = "creating"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


class Config:
    """Configuration constants for Par."""

    # Repository and session naming
    REPO_ID_LENGTH = 8
    REPO_ID_FULL_LENGTH = 12
    SESSION_NAME_MAX_LENGTH = 15
    WORKSPACE_ID_LENGTH = 8
    TMUX_SESSION_PREFIX = "par"
    WORKSPACE_SESSION_PREFIX = "par-ws"

    # State management
    STATE_CACHE_TTL = 30  # seconds
    SESSION_STATE_FILE = "state.json"
    WORKSPACE_STATE_FILE = "workspaces.json"

    # Security limits
    MAX_SESSION_NAME_LENGTH = 64
    MAX_BRANCH_NAME_LENGTH = 255
    MAX_COMMAND_LENGTH = 1000

    # File paths
    DATA_DIR_NAME = "par"
    WORKTREES_DIR_NAME = "worktrees"
    WORKSPACES_DIR_NAME = "workspaces"

    # Validation patterns
    VALID_SESSION_NAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"
    VALID_BRANCH_NAME_PATTERN = r"^[a-zA-Z0-9_./%-]+$"
    VALID_PANE_PATTERN = r"^[0-9]+$"

    # Forbidden patterns in branch names
    FORBIDDEN_BRANCH_PATTERNS = ["..", "//", "--", "\\"]

    # Par configuration file
    PAR_CONFIG_FILE = ".par.yaml"

    # Control characters to remove from commands
    FORBIDDEN_CONTROL_CHARS = ["\0", "\x1b"]


class Colors:
    """Color constants for terminal output."""

    SUCCESS = "green"
    ERROR = "red"
    WARNING = "yellow"
    INFO = "cyan"
    HIGHLIGHT = "bold"


class Messages:
    """Common message templates."""

    SESSION_EXISTS = "Error: Session '{label}' already exists."
    WORKSPACE_EXISTS = "Error: Workspace '{label}' already exists."
    SESSION_NOT_FOUND = "Error: Session '{label}' not found."
    WORKSPACE_NOT_FOUND = "Error: Workspace '{label}' not found."
    NOT_IN_GIT_REPO = "Error: Not in a git repository."
    TMUX_NOT_AVAILABLE = "Error: tmux not available or not running."
    INVALID_INPUT = "Invalid input: {error}"

    # Success messages
    CREATED_WORKTREE = "Created worktree '{label}' at {path}"
    CREATED_SESSION = "Created tmux session '{session}'"
    DELETED_BRANCH = "Deleted branch '{branch}'"
    SENT_COMMAND = "Sent command to session '{session}'"
