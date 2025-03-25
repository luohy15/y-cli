# MCP Daemon

The MCP (Model Context Protocol) Daemon is a standalone background process that maintains persistent connections to MCP servers. This eliminates the need to reconnect to MCP servers each time a new chat session is started.

## Benefits

- **Persistent Connections**: MCP servers remain connected between chat sessions
- **Improved Performance**: Eliminates connection overhead for each new chat
- **Consistent State**: Ensures MCP servers maintain consistent state across chats
- **Resource Efficiency**: Reduces resource usage by sharing connections
- **Concurrent Requests**: Supports multiple simultaneous client requests through connection pooling

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
4. The daemon manages a connection pool to handle concurrent requests
5. If the daemon is not running, chat sessions fall back to direct connections

## Connection Pooling

The daemon client supports concurrent requests through connection pooling:

- **Default Pool Size**: 5 connections
- **Configurable Pool Size**: Can be adjusted via constructor or environment variable
- **Auto-Scaling**: Creates connections on demand up to the configured pool size
- **Connection Reuse**: Efficiently reuses connections for better performance

### Configuring Pool Size

You can configure the connection pool size in two ways:

1. **Environment Variable**:
   ```bash
   # Set pool size to 10
   export Y_CLI_MCP_DAEMON_POOL_SIZE=10
   ```

2. **Programmatically** (when using the client in code):
   ```python
   from mcp_server.daemon_client import MCPDaemonClient
   
   # Create client with custom pool size
   client = MCPDaemonClient(pool_size=10)
   ```

### Testing Concurrent Requests

A test script is provided to verify that the connection pool properly handles concurrent requests:

```bash
# Run with default settings (10 requests, pool size 5)
python build/test_concurrent_daemon.py

# Run with custom parameters: 20 requests, pool size 8
python build/test_concurrent_daemon.py 20 8
```

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

### Concurrent Request Errors

- If you see "readuntil() called while another coroutine is already waiting for incoming data" errors:
  - This indicates multiple requests are trying to use the same connection
  - Verify that your client is using the latest version with connection pooling
  - Try setting a larger pool size via the `Y_CLI_MCP_DAEMON_POOL_SIZE` environment variable
  - Check if your code is properly releasing connections back to the pool
