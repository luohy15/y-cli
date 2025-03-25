import asyncio
from typing import Tuple

class ConnectionPool:
    """
    Manages a pool of connections to the MCP daemon server.
    Handles connection creation, acquisition, and release.
    """
    def __init__(self, socket_path: str, pool_size: int = 5):
        """
        Initialize the connection pool.
        
        Args:
            socket_path (str): Path to the Unix socket for IPC.
            pool_size (int): Maximum number of connections in the pool.
        """
        self.socket_path = socket_path
        self.pool_size = pool_size
        self.available_connections = asyncio.Queue()
        self.active_connections = 0
        self.pool_lock = asyncio.Lock()
        
    async def initialize(self):
        """
        Initialize the connection pool.
        This doesn't pre-create connections but sets up the pool.
        """
        pass
        
    async def get_connection(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Get a connection from the pool or create a new one if needed.
        
        Returns:
            Tuple[asyncio.StreamReader, asyncio.StreamWriter]: Connection pair.
        """
        # First, try to get an available connection from the pool
        try:
            return await asyncio.wait_for(self.available_connections.get(), 0.1)
        except asyncio.TimeoutError:
            # No connections available in the queue, check if we can create a new one
            async with self.pool_lock:
                if self.active_connections < self.pool_size:
                    # We can create a new connection
                    self.active_connections += 1
                    try:
                        reader, writer = await asyncio.open_unix_connection(self.socket_path)
                        return reader, writer
                    except Exception as e:
                        # If connection creation fails, decrement counter
                        self.active_connections -= 1
                        raise e
                else:
                    # Pool is full, wait for a connection to be released
                    pass
            
            # Wait for an available connection
            return await self.available_connections.get()
            
    async def release_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Release a connection back to the pool.
        
        Args:
            reader (asyncio.StreamReader): The reader part of the connection.
            writer (asyncio.StreamWriter): The writer part of the connection.
        """
        # Check if connection is still valid
        if writer.is_closing():
            async with self.pool_lock:
                self.active_connections -= 1
            return
            
        # Return to the pool
        await self.available_connections.put((reader, writer))
        
    async def close_all(self):
        """Close all connections in the pool."""
        # Close all available connections
        while not self.available_connections.empty():
            _, writer = await self.available_connections.get()
            writer.close()
            await writer.wait_closed()
            
        # Reset counters
        async with self.pool_lock:
            self.active_connections = 0