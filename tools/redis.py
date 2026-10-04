"""Redis health and performance metrics via INFO command."""
import os
from typing import Optional, Dict
import redis
from auth.credentials import get_credentials_manager


class RedisClient:
    """Redis client for fetching metrics via INFO command."""

    def __init__(self, host: str = None, port: int = None, password: str = None, db: int = 0, redis_name: str = None):
        """
        Initialize Redis connection.

        Args:
            host: Redis host (if provided, use directly; otherwise fetch from credentials manager)
            port: Redis port
            password: Redis password
            db: Redis database number
            redis_name: "redis-cache-1", "redis-cache-2", etc. (used to fetch from credentials manager)
        """
        # If host not provided, try to fetch from credentials manager
        if not host and redis_name:
            creds_manager = get_credentials_manager()
            creds = creds_manager.get_redis_credentials(redis_name)
            host = creds.get("host")
            port = creds.get("port", port)
            password = creds.get("password", password)
            db = creds.get("db", db)

        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.db = db

        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # Test connection
            self.client.ping()
        except Exception as e:
            raise Exception(f"Failed to connect to Redis at {self.host}:{self.port}: {str(e)}")

    def get_metrics(self) -> Dict:
        """
        Fetch all Redis metrics from INFO command.

        Returns:
            dict with memory_percent, connected_clients, eviction_rate, hit_rate, etc.
        """
        try:
            info = self.client.info()

            # Memory metrics
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)
            memory_percent = (used_memory / max_memory * 100) if max_memory > 0 else 0

            # Connection metrics
            connected_clients = info.get("connected_clients", 0)
            # Note: maxclients is a config parameter, not directly in INFO
            # We'll use a reasonable default if not available
            max_clients_config = info.get("maxclients", 1000)

            # Eviction metrics
            evicted_keys = info.get("evicted_keys", 0)
            # Calculate eviction rate (evictions per second, approximate)
            # We could track this over time, but for now just report total evicted
            total_evictions = evicted_keys

            # Hit rate
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total_requests = hits + misses
            hit_rate = (hits / total_requests) if total_requests > 0 else 0

            # Throughput
            commands_per_sec = info.get("instantaneous_ops_per_sec", 0)

            return {
                "memory_percent": round(memory_percent, 2),
                "memory_used_mb": round(used_memory / (1024 * 1024), 2),
                "memory_max_mb": round(max_memory / (1024 * 1024), 2) if max_memory > 0 else 0,
                "connected_clients": connected_clients,
                "connected_clients_max": max_clients_config,
                "eviction_rate": total_evictions,  # total evicted keys
                "hit_rate": round(hit_rate, 4),
                "commands_per_sec": round(commands_per_sec, 2),
                "timestamp": None,
            }
        except Exception as e:
            print(f"Error fetching Redis metrics: {e}")
            raise


def get_redis_metrics(config: dict = None) -> Dict:
    """
    Fetch Redis metrics from config or credentials manager.

    Args:
        config: Redis configuration from service YAML, should contain:
                - host: Redis hostname (if not provided, fetches from credentials manager)
                - port: Redis port
                - password: Redis password (optional, fetches from credentials manager if not provided)
                - db: Redis database number (optional)
                - name: Redis instance name (used to fetch from credentials manager, e.g., "redis-cache-1")

    Returns:
        dict with memory_percent, connected_clients, eviction_rate, etc.
    """
    if not config:
        config = {}

    try:
        host = config.get("host")
        port = config.get("port")
        password = config.get("password")
        db = config.get("db", 0)
        redis_name = config.get("name")  # e.g., "redis-cache-1"

        # If password not provided in config, fetch credentials (host/port/password) from credentials manager
        if not password and redis_name:
            creds_manager = get_credentials_manager()
            creds = creds_manager.get_redis_credentials(redis_name)
            host = host or creds.get("host")
            port = port or creds.get("port")
            password = creds.get("password")
            db = creds.get("db", db)

        # Use provided config or env vars as final fallback
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = port or int(os.getenv("REDIS_PORT", 6379))
        password = password or os.getenv("REDIS_PASSWORD")
        client = RedisClient(host=host, port=port, password=password, db=db)

        return client.get_metrics()
    except Exception as e:
        print(f"Error initializing Redis client: {e}")
        return {
            "memory_percent": None,
            "memory_used_mb": None,
            "memory_max_mb": None,
            "connected_clients": None,
            "connected_clients_max": None,
            "eviction_rate": None,
            "hit_rate": None,
            "commands_per_sec": None,
            "timestamp": None,
        }
