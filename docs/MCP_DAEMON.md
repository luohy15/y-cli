# MCP Daemon

The MCP (Model Context Protocol) Daemon is a standalone background process that maintains persistent connections to MCP servers. This eliminates the need to reconnect to MCP servers each time a new chat session is started.

## Benefits

- **Persistent Connections**: MCP servers remain connected between chat sessions
- **Improved Performance**: Eliminates connection overhead for each new chat
- **Consistent State**: Ensures MCP servers maintain consistent state across chats
- **Resource Efficiency**: Reduces resource usage by sharing connections

## Usage

The MCP daemon can be managed using the `y-cli mcp daemon` command with various subcommands:

### Starting the Daemon

```bash
# Start the daemon in the background
y-cli mcp daemon start

# Start the daemon in the foreground (useful for debugging)
y-cli mcp daemon start --foreground

# Start with custom socket and log paths
y-cli mcp daemon start --socket /path/to/socket --log /path/to/logfile.log
```

### Checking Daemon Status

```bash
# Check if the daemon is running and list connected servers
y-cli mcp daemon status
```

### Viewing Daemon Logs

```bash
# Show the last 20 lines of the daemon log
y-cli mcp daemon log

# Show the last N lines of the daemon log
y-cli mcp daemon log --lines 50
```

### Stopping the Daemon

```bash
# Stop the daemon
y-cli mcp daemon stop
```

### Restarting the Daemon

```bash
# Restart the daemon
y-cli mcp daemon restart

# Restart the daemon in foreground mode
y-cli mcp daemon restart --foreground
```

## How It Works

1. The daemon process starts and connects to all configured MCP servers
2. It creates a Unix socket (or named pipe on Windows) for IPC communication
3. Chat sessions connect to the daemon via this socket to execute MCP tools
4. If the daemon is not running, chat sessions fall back to direct connections

## File Locations

- **Socket**: `~/Library/Application Support/y-cli/mcp_daemon.sock` (macOS) or `~/.local/share/y-cli/mcp_daemon.sock` (Linux)
- **PID File**: `~/Library/Application Support/y-cli/mcp_daemon.pid` (macOS) or `~/.local/share/y-cli/mcp_daemon.pid` (Linux)
- **Log File**: `~/Library/Logs/y-cli/mcp_daemon.log` (macOS) or `~/.local/share/y-cli/logs/mcp_daemon.log` (Linux)

## Troubleshooting

### Daemon Won't Start

- Check the log file for errors
- Ensure the socket path is valid and accessible
- Verify you have the necessary permissions

### Connection Issues

- Check if the daemon is running with `y-cli mcp daemon status`
- Verify the socket file exists
- Restart the daemon with `y-cli mcp daemon restart`

### MCP Servers Not Connecting

- Check the daemon log for connection errors
- Verify the MCP server configurations are correct
- Try restarting the daemon with `y-cli mcp daemon restart`
