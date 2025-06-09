# Cloudflare D1 for y-cli

This document provides information on using Cloudflare D1 as a storage solution for y-cli chat data.

## Overview

Cloudflare D1 is a SQLite-compatible database service on Cloudflare's edge network, providing global distribution and low-latency access for y-cli chat data.

## Configuration

Add the following to your y-cli config file:

```yaml
storage_type: cloudflare_d1
cloudflare_d1:
  account_id: <your-cloudflare-account-id>
  database_id: <your-d1-database-id>
  api_token: <your-cloudflare-api-token>
  user_prefix: <optional-user-prefix>  # Defaults to "default"
```

### Obtaining Credentials

1. Log in to [Cloudflare dashboard](https://dash.cloudflare.com)
2. Navigate to Workers & Pages → D1
3. Create or select a database and note its ID
4. Create an API token with D1 access permissions

## Implementation

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_prefix TEXT NOT NULL, 
    chat_id TEXT NOT NULL, 
    json_content TEXT NOT NULL, 
    update_time TEXT,
    UNIQUE(user_prefix, chat_id)
);
```

### Client Classes

The implementation consists of two main classes:

1. **D1Database**: Connects to Cloudflare's D1 API and executes SQL statements
2. **PreparedStatement**: Represents a SQL statement with parameter binding

#### D1Database Usage

```python
from chat.repository.cloudflare_d1_client import D1Database

# Initialize the client
db = D1Database(
    database_id="your-database-id",  # Optional, defaults to config
    api_token="your-api-token"       # Optional, defaults to config
)

# Execute a direct SQL statement
result = await db.exec("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")

# Prepare and execute a statement with parameters
user = await db.prepare("SELECT * FROM users WHERE name = ?").bind("Alice").first()
```

#### PreparedStatement Methods

- `bind(*args)`: Binds parameters to the statement
- `first()`: Returns the first row or None
- `all()`: Returns all rows
- `run()`: Executes non-query statements (INSERT, UPDATE, DELETE)

## Migration

To migrate from other storage types:

```bash
# Export chats from current storage
y-cli chat export --output chats.json

# Change your configuration to use Cloudflare D1

# Import chats to the new storage
y-cli chat import --input chats.json
```

## Troubleshooting

### Connection Issues

If experiencing connection problems:
- Verify API token permissions
- Confirm database ID is correct
- Check network connectivity to Cloudflare's API

### Missing Configuration Warning

If you see:
```
Warning: Missing cloudflare_d1 configuration: database_id, api_token
Falling back to file-based storage
```
Ensure all required configuration parameters are set correctly.

## Limitations

- Requires internet connectivity
- Subject to Cloudflare's rate limits and quotas
- Complex data types are automatically converted to JSON strings
- Currently doesn't support complex SQL queries for advanced filtering
