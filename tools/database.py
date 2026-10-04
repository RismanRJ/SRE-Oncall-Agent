"""Database health and performance metrics via pg_stat_activity (writer instance only)."""
import os
from typing import Optional, Dict
import psycopg2
import psycopg2.extras
from auth.credentials import get_credentials_manager


class DatabaseClient:
    """Postgres client for fetching connection/health metrics from the writer instance."""

    def __init__(self, host: str = None, port: int = None, username: str = None,
                 password: str = None, database: str = None, db_name: str = None):
        """
        Args:
            host: Writer instance host (if provided, use directly; otherwise fetch from credentials manager)
            port: Postgres port
            username: DB username
            password: DB password
            database: DB name
            db_name: "aurora-primary", etc. (used to fetch from credentials manager)
        """
        if not host and db_name:
            creds_manager = get_credentials_manager()
            creds = creds_manager.get_database_credentials(db_name)
            host = creds.get("host")
            port = creds.get("port", port)
            username = creds.get("username", username)
            password = creds.get("password", password)
            database = creds.get("database", database)

        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port or int(os.getenv("POSTGRES_PORT", 5432))
        self.username = username or os.getenv("POSTGRES_USERNAME", "monitoring_user")
        self.password = password or os.getenv("POSTGRES_PASSWORD")
        self.database = database or os.getenv("POSTGRES_DATABASE", "snitch_prod")

        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                dbname=self.database,
                connect_timeout=5,
            )
            self.conn.autocommit = True
        except Exception as e:
            raise Exception(f"Failed to connect to Postgres at {self.host}:{self.port}: {str(e)}")

    def _query(self, sql: str):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            return cur.fetchall()

    def get_metrics(self) -> Dict:
        """
        Fetch connection and health metrics from pg_stat_activity (writer only).

        Returns:
            dict with active_connections_percent, slow_query_count, connection metrics, etc.
        """
        try:
            total_row = self._query("SELECT count(*) AS total FROM pg_stat_activity;")
            active_row = self._query("SELECT count(*) AS active FROM pg_stat_activity WHERE state = 'active';")
            idle_row = self._query("SELECT count(*) AS idle FROM pg_stat_activity WHERE state = 'idle';")
            idle_in_tx_row = self._query(
                "SELECT count(*) AS idle_in_tx FROM pg_stat_activity WHERE state = 'idle in transaction';"
            )
            max_conn_row = self._query("SHOW max_connections;")
            slow_row = self._query(
                """
                SELECT count(*) AS slow_count
                FROM pg_stat_activity
                WHERE state = 'active'
                  AND now() - query_start > interval '5 seconds';
                """
            )
            cache_row = self._query(
                """
                SELECT
                  sum(blks_hit) AS hits,
                  sum(blks_hit) + sum(blks_read) AS total
                FROM pg_stat_database
                WHERE datname = current_database();
                """
            )

            total_connections = total_row[0]["total"]
            active_connections = active_row[0]["active"]
            idle_connections = idle_row[0]["idle"]
            idle_in_transaction = idle_in_tx_row[0]["idle_in_tx"]
            max_connections = int(max_conn_row[0]["max_connections"])
            slow_query_count = slow_row[0]["slow_count"]

            hits = float(cache_row[0]["hits"] or 0)
            total_reads = float(cache_row[0]["total"] or 0)
            cache_hit_ratio = (hits / total_reads) if total_reads > 0 else 0

            active_connections_percent = (
                (total_connections / max_connections * 100) if max_connections > 0 else 0
            )

            return {
                "active_connections_percent": round(active_connections_percent, 2),
                "total_connections": total_connections,
                "active_connections": active_connections,
                "idle_connections": idle_connections,
                "idle_in_transaction": idle_in_transaction,
                "max_connections": max_connections,
                "slow_query_count": slow_query_count,
                "cache_hit_ratio": round(cache_hit_ratio, 4),
                "timestamp": None,
            }
        except Exception as e:
            print(f"Error fetching database metrics: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()


def get_database_metrics(config: dict = None) -> Dict:
    """
    Fetch database metrics from config or credentials manager. Always targets the writer instance.

    Args:
        config: Database configuration from service YAML, should contain:
                - host: Writer instance hostname (if not provided, fetches from credentials manager)
                - port, username, password, database (optional, fetched from credentials manager if not provided)
                - name: DB instance name (used for credentials manager lookup, e.g., "aurora-primary")

    Returns:
        dict with active_connections_percent, slow_query_count, etc.
    """
    if not config:
        config = {}

    client = None
    try:
        host = config.get("host")
        port = config.get("port")
        username = config.get("username")
        password = config.get("password")
        database = config.get("database")
        db_name = config.get("name")  # e.g., "aurora-primary"

        if not password and db_name:
            creds_manager = get_credentials_manager()
            creds = creds_manager.get_database_credentials(db_name)
            host = host or creds.get("host")
            port = port or creds.get("port")
            username = username or creds.get("username")
            password = creds.get("password")
            database = database or creds.get("database")

        host = host or os.getenv("POSTGRES_HOST", "localhost")
        port = port or int(os.getenv("POSTGRES_PORT", 5432))
        username = username or os.getenv("POSTGRES_USERNAME", "monitoring_user")
        password = password or os.getenv("POSTGRES_PASSWORD")
        database = database or os.getenv("POSTGRES_DATABASE", "snitch_prod")

        client = DatabaseClient(host=host, port=port, username=username, password=password, database=database)
        metrics = client.get_metrics()

        # Fetch CPU + instance count from CloudWatch/RDS if configured
        aws_config = config.get("aws")
        if aws_config:
            from tools.cloudwatch import get_rds_cpu, get_rds_cluster_members
            region = aws_config.get("region")
            writer_id = aws_config.get("rds_writer_instance_identifier")
            cluster_id = aws_config.get("rds_cluster_identifier")
            if writer_id:
                metrics["cpu_percent"] = get_rds_cpu(writer_id, region=region)
            if cluster_id:
                members = get_rds_cluster_members(cluster_id, region=region)
                metrics["instance_count"] = len(members) if members is not None else None
                readers = [m for m in (members or []) if m["identifier"] != writer_id]
                metrics["readers"] = [
                    {"identifier": r["identifier"], "cpu_percent": get_rds_cpu(r["identifier"], region=region)}
                    for r in readers
                ]

        return metrics
    except Exception as e:
        print(f"Error initializing Database client: {e}")
        return {
            "active_connections_percent": None,
            "total_connections": None,
            "active_connections": None,
            "idle_connections": None,
            "idle_in_transaction": None,
            "max_connections": None,
            "slow_query_count": None,
            "cache_hit_ratio": None,
            "cpu_percent": None,
            "instance_count": None,
            "readers": None,
            "timestamp": None,
        }
    finally:
        if client:
            client.close()
