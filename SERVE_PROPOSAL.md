# Par Serve: Development Server Management

## Overview

`par serve` extends par's session and workspace management to include development server orchestration. This solves the common problem of managing multiple development servers across repositories while maintaining par's philosophy of isolated, manageable development environments.

## Problem Statement

Current development workflow pain points:

1. **Manual Server Management** - Developers manually start/stop multiple servers
2. **Context Switching** - Remembering which servers are needed for each feature
3. **Port Conflicts** - Accidental conflicts between different development sessions
4. **Inconsistent Setup** - New developers struggle with server startup sequences
5. **Workspace Complexity** - Multi-repo projects require coordinating servers across repositories

## Proposed Solution

Extend `.par.yaml` configuration to include server definitions and add `par serve` commands for unified server lifecycle management.

## Configuration Schema

### Basic Server Configuration

```yaml
# .par.yaml
servers:
  frontend:
    command: "npm run dev"
    working_directory: "frontend"
    port: 3000
    health_check: "http://localhost:3000"
    auto_start: true
    
  backend:
    command: "python manage.py runserver"
    working_directory: "backend" 
    port: 8000
    health_check: "http://localhost:8000/health"
    auto_start: true
    
  storybook:
    command: "npm run storybook"
    working_directory: "frontend"
    port: 6006
    auto_start: false
    
  database:
    command: "docker-compose up postgres"
    port: 5432
    auto_start: true
    depends_on: []  # No dependencies
    
  api:
    command: "uvicorn main:app --reload"
    working_directory: "backend"
    port: 8001
    depends_on: ["database"]  # Start after database
    auto_start: true
```

### Advanced Configuration

```yaml
servers:
  frontend:
    command: "npm run dev"
    working_directory: "frontend"
    port: 3000
    env:
      VITE_API_URL: "http://localhost:8000"
      NODE_ENV: "development"
    health_check: 
      url: "http://localhost:3000"
      timeout: 30
      retries: 3
    auto_start: true
    restart_on_failure: true
    startup_delay: 2  # seconds
    
  backend:
    command: ["python", "manage.py", "runserver", "0.0.0.0:8000"]
    working_directory: "backend"
    port: 8000
    env:
      DEBUG: "true"
      DATABASE_URL: "postgresql://localhost:5432/myapp_dev"
    health_check:
      url: "http://localhost:8000/health"
    auto_start: true
    depends_on: ["database"]
    pre_start:
      - "python manage.py migrate"
      - "python manage.py collectstatic --noinput"
```

## Command Interface

### Session Server Management

```bash
# Start servers for a session
par serve <session-label>                    # Start all auto_start servers
par serve <session-label> --all              # Start all servers (including auto_start: false)
par serve <session-label> --only frontend    # Start specific server
par serve <session-label> --only frontend,backend  # Start multiple specific servers

# Stop servers
par stop <session-label>                     # Stop all servers
par stop <session-label> --only backend     # Stop specific server

# Server status and management
par status <session-label>                   # Show all server status
par status <session-label> frontend         # Show specific server status
par logs <session-label> frontend           # Show server logs
par restart <session-label> backend         # Restart specific server
```

### Workspace Server Management

```bash
# Start servers across all repositories in workspace
par workspace serve <workspace-label>                          # All auto_start servers
par workspace serve <workspace-label> --all                    # All servers
par workspace serve <workspace-label> --only coplane/frontend  # Specific repo/server

# Stop workspace servers
par workspace stop <workspace-label>                           # Stop all servers
par workspace stop <workspace-label> --only planar/backend     # Stop specific servers

# Workspace server status
par workspace status <workspace-label>                         # All workspace servers
par workspace logs <workspace-label> coplane/frontend          # Specific repo/server logs
```

### Global Server Management

```bash
# Overview of all servers across sessions/workspaces
par servers                                  # List all running servers
par servers --sessions                       # Show servers by session
par servers --ports                          # Show port usage
par servers kill-all                         # Emergency stop all servers
```

## Implementation Architecture

### 1. Configuration Loading

```python
@dataclass
class ServerConfig:
    name: str
    command: Union[str, List[str]]
    working_directory: Optional[str] = None
    port: Optional[int] = None
    env: Dict[str, str] = field(default_factory=dict)
    health_check: Optional[Union[str, Dict]] = None
    auto_start: bool = True
    restart_on_failure: bool = False
    startup_delay: int = 0
    depends_on: List[str] = field(default_factory=list)
    pre_start: List[str] = field(default_factory=list)

@dataclass  
class HealthCheckConfig:
    url: str
    timeout: int = 10
    retries: int = 3
    interval: int = 5

def load_server_configs(par_config: Dict) -> List[ServerConfig]:
    """Parse server configurations from .par.yaml"""
    servers = par_config.get("servers", {})
    return [ServerConfig(name=name, **config) for name, config in servers.items()]
```

### 2. Server State Management

```python
@dataclass
class ServerInstance:
    config: ServerConfig
    pid: Optional[int] = None
    tmux_pane: Optional[str] = None
    status: str = "stopped"  # stopped, starting, running, failed
    started_at: Optional[datetime] = None
    port: Optional[int] = None
    health_status: str = "unknown"  # unknown, healthy, unhealthy
    restart_count: int = 0

class ServerManager:
    def __init__(self, session_name: str, worktree_path: Path):
        self.session_name = session_name
        self.worktree_path = worktree_path
        self.servers: Dict[str, ServerInstance] = {}
        
    async def start_server(self, server_name: str) -> bool:
        """Start a specific server"""
        
    async def stop_server(self, server_name: str) -> bool:
        """Stop a specific server"""
        
    async def restart_server(self, server_name: str) -> bool:
        """Restart a specific server"""
        
    async def get_server_status(self, server_name: str) -> ServerInstance:
        """Get current server status"""
        
    async def health_check_all(self) -> Dict[str, bool]:
        """Run health checks on all servers"""
```

### 3. Tmux Integration Strategy

**Option A: Dedicated Server Panes**
```
Session Layout:
┌─────────────────┬───────────────┬──────────────┐
│                 │   frontend    │   backend    │
│   Main Dev      │   Server      │   Server     │
│   Terminal      │   (npm dev)   │  (django)    │
│                 │               │              │
└─────────────────┴───────────────┴──────────────┘
```

**Option B: Background Processes with Log Aggregation**
```
Session Layout:
┌─────────────────────────────────────────────────┐
│                                                 │
│              Main Dev Terminal                  │
│                                                 │
│  Servers running in background                  │
│  Logs available via: par logs <session> <srv>  │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Recommended: Hybrid Approach**
- Auto-start servers run as background processes
- Manual/debug servers get dedicated panes
- Configurable per server via `display_mode: "pane" | "background"`

### 4. Startup Dependency Resolution

```python
class DependencyResolver:
    def resolve_startup_order(self, servers: List[ServerConfig]) -> List[List[str]]:
        """
        Resolve server startup order based on dependencies.
        Returns list of lists where each inner list can start in parallel.
        
        Example: [[database], [backend, cache], [frontend]]
        """
        
    def validate_dependencies(self, servers: List[ServerConfig]) -> List[str]:
        """Validate no circular dependencies exist"""
```

### 5. Health Checking

```python
class HealthChecker:
    async def check_http_endpoint(self, url: str, timeout: int = 10) -> bool:
        """Check if HTTP endpoint responds with 2xx status"""
        
    async def check_port_listening(self, port: int) -> bool:
        """Check if port is accepting connections"""
        
    async def check_process_running(self, pid: int) -> bool:
        """Check if process is still running"""
        
    async def run_health_check(self, server: ServerInstance) -> bool:
        """Run appropriate health check for server"""
```

## Integration with Existing Features

### Critical Requirement: Initialization-First Server Startup

**Servers MUST only start after initialization has completed.** This ensures:

- Dependencies are installed before servers attempt to start
- Environment files exist before servers read them  
- Database migrations complete before API servers start
- Build processes finish before development servers launch

### 1. Session Lifecycle Integration

```python
def start_session(label: str, open_session: bool = False, auto_serve: bool = True):
    """Enhanced session start with initialization-first server startup"""
    # 1. Create worktree and tmux session
    operations.create_worktree(label, worktree_path)
    operations.create_tmux_session(session_name, worktree_path)
    
    # 2. Run initialization commands FIRST
    config = initialization.load_par_config(repo_root)
    if config:
        initialization.run_initialization(config, session_name, worktree_path)
        
        # 3. ONLY start servers after initialization completes successfully
        if auto_serve and "servers" in config:
            server_manager = ServerManager(session_name, worktree_path)
            asyncio.run(server_manager.start_auto_servers(config["servers"]))
    
def remove_session(label: str):
    """Enhanced session removal with server cleanup"""
    session_data = sessions.get(label)
    if session_data:
        # Stop all servers before cleanup
        server_manager = ServerManager(session_data["tmux_session_name"], Path(session_data["worktree_path"]))
        asyncio.run(server_manager.stop_all_servers())
    
    # ... existing removal logic ...
```

### 2. Workspace Integration

```python
def start_workspace_session(label: str, repos: Optional[List[str]] = None, open_session: bool = False, auto_serve: bool = True):
    """Enhanced workspace start with initialization-first server orchestration"""
    # 1. Create worktrees and tmux session for all repos
    # ... existing workspace creation logic ...
    
    # 2. Run initialization for each repository FIRST
    for repo_data in repos_data:
        repo_path = Path(repo_data["repo_path"])
        worktree_path = Path(repo_data["worktree_path"])
        config = initialization.load_par_config(repo_path)
        if config:
            initialization.run_initialization(config, session_name, worktree_path, workspace_mode=True)
    
    # 3. ONLY start servers after ALL initialization completes
    if auto_serve:
        for repo_data in repos_data:
            repo_config = initialization.load_par_config(Path(repo_data["repo_path"]))
            if repo_config and "servers" in repo_config:
                server_manager = ServerManager(f"{session_name}-{repo_data['repo_name']}", Path(repo_data["worktree_path"]))
                asyncio.run(server_manager.start_auto_servers(repo_config["servers"]))
```

### 3. Control Center Enhancement

```bash
par control-center --with-servers
```

Shows server status in control center view:
```
┌─────────────────┬─────────────────┬─────────────────┐
│   Session 1     │   Session 2     │   Session 3     │
│   ● frontend:✓  │   ● backend:✓   │   ● api:✗       │
│   ● backend:✓   │   ● db:✓        │   ● ui:✓        │
└─────────────────┴─────────────────┴─────────────────┘
```

## Configuration Examples

### Full-Stack Web Application

```yaml
initialization:
  commands:
    - name: "Install frontend deps"
      command: "npm install"
      working_directory: "frontend"
    - name: "Install backend deps"  
      command: "pip install -r requirements.txt"
      working_directory: "backend"

servers:
  database:
    command: "docker-compose up -d postgres"
    port: 5432
    health_check: "tcp://localhost:5432"
    auto_start: true
    
  backend:
    command: "python manage.py runserver"
    working_directory: "backend"
    port: 8000
    env:
      DEBUG: "true"
      DATABASE_URL: "postgresql://localhost:5432/myapp"
    health_check: "http://localhost:8000/health"
    depends_on: ["database"]
    pre_start:
      - "python manage.py migrate"
    auto_start: true
    
  frontend:
    command: "npm run dev"
    working_directory: "frontend"
    port: 3000
    env:
      VITE_API_URL: "http://localhost:8000"
    health_check: "http://localhost:3000"
    depends_on: ["backend"]
    auto_start: true
    
  storybook:
    command: "npm run storybook"
    working_directory: "frontend"
    port: 6006
    auto_start: false
```

### Microservices with Docker

```yaml
servers:
  redis:
    command: "docker run --rm -p 6379:6379 redis:alpine"
    port: 6379
    health_check: "tcp://localhost:6379"
    auto_start: true
    
  auth-service:
    command: "npm start"
    working_directory: "services/auth"
    port: 3001
    env:
      REDIS_URL: "redis://localhost:6379"
    depends_on: ["redis"]
    auto_start: true
    
  user-service:
    command: "npm start"
    working_directory: "services/users"
    port: 3002
    depends_on: ["redis", "auth-service"]
    auto_start: true
    
  api-gateway:
    command: "npm start"
    working_directory: "gateway"
    port: 3000
    env:
      AUTH_SERVICE_URL: "http://localhost:3001"
      USER_SERVICE_URL: "http://localhost:3002"
    depends_on: ["auth-service", "user-service"]
    auto_start: true
```

## Benefits

1. **Unified Development Experience** - One command starts entire development environment
2. **Project-Specific Configuration** - Server setup lives with the project
3. **Dependency Management** - Automatic startup ordering
4. **Health Monitoring** - Built-in server health checks
5. **Multi-Repo Support** - Works seamlessly with workspaces
6. **Developer Onboarding** - New developers get working environment immediately
7. **Context Isolation** - Different sessions/workspaces don't interfere

## Implementation Phases

### Phase 1: Basic Server Management
- [ ] Basic server configuration parsing
- [ ] Simple start/stop commands for sessions
- [ ] Background process management
- [ ] Basic health checking (port-based)

### Phase 2: Advanced Features  
- [ ] Dependency resolution and startup ordering
- [ ] HTTP health checks with retries
- [ ] Environment variable injection
- [ ] Pre-start commands

### Phase 3: Workspace Integration
- [ ] Multi-repo server management
- [ ] Workspace server status aggregation
- [ ] Cross-repo dependency handling

### Phase 4: Enhanced UX
- [ ] Server log aggregation and streaming
- [ ] Control center server status integration
- [ ] Auto-restart on failure
- [ ] Server performance metrics

## Considerations & Questions

### Technical Considerations

1. **Process Management** - How to reliably track and clean up background processes?
2. **Port Conflicts** - How to handle port conflicts between sessions/workspaces?
3. **Resource Usage** - Should we limit server resource consumption?
4. **Platform Support** - How to handle Windows/macOS/Linux differences?

### User Experience Questions

1. **Default Behavior** - Should servers auto-start by default when creating sessions?
2. **Failure Handling** - What happens when a server fails to start or crashes?
3. **Configuration Complexity** - How to balance power with simplicity?
4. **Migration Path** - How do existing users adopt this feature?

### Integration Questions

1. **Docker Support** - Should we have first-class Docker container support?
2. **IDE Integration** - Can we integrate with IDE run configurations?
3. **Monitoring** - Should we integrate with external monitoring tools?
4. **Testing** - How does this interact with test runners?

## Future Enhancements

- **Load Balancing** - Multiple instances of the same server
- **Environment Switching** - Different server configs for dev/staging/prod
- **Service Discovery** - Automatic service registration and discovery
- **Metrics Collection** - Built-in performance and health metrics
- **Integration Testing** - Automated health checks and integration tests
- **Cloud Integration** - Support for cloud development environments

---

This proposal establishes `par serve` as a natural extension of par's session and workspace management, providing a unified development server orchestration system that scales from single repositories to complex multi-service architectures.