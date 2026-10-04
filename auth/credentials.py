"""
Credentials manager that reads from AWS Secrets Manager or environment variables.
In production: fetch from Secrets Manager ARN
In testing: fallback to environment variables
"""
import os
import json
from typing import Optional

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class CredentialsManager:
    """Manage credentials from AWS Secrets Manager or env vars."""

    def __init__(self):
        self.use_aws_secrets = os.getenv("USE_AWS_SECRETS", "false").lower() == "true"
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        if self.use_aws_secrets:
            if not HAS_BOTO3:
                print("Warning: boto3 not installed, falling back to environment variables")
                self.use_aws_secrets = False
                self.secrets_client = None
            else:
                self.secrets_client = boto3.client("secretsmanager", region_name=self.aws_region)
        else:
            self.secrets_client = None

    def get_secret(self, secret_id: str) -> Optional[dict]:
        """
        Get secret from AWS Secrets Manager or environment variable.

        Args:
            secret_id: ARN (production) or env var name (testing)
                      e.g., "arn:aws:secretsmanager:us-east-1:123456789:secret:redis-cache-1"
                      or "REDIS_CACHE_1_CREDENTIALS"

        Returns:
            dict with credentials, or None if not found
        """
        if self.use_aws_secrets:
            return self._get_from_aws_secrets(secret_id)
        else:
            return self._get_from_env(secret_id)

    def _get_from_aws_secrets(self, secret_arn: str) -> Optional[dict]:
        """Fetch secret from AWS Secrets Manager."""
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            secret_string = response.get("SecretString")
            if secret_string:
                return json.loads(secret_string)
            return None
        except Exception as e:
            print(f"Error fetching secret {secret_arn} from AWS: {e}")
            return None

    def _get_from_env(self, env_var_name: str) -> Optional[dict]:
        """Fetch secret from environment variable (testing mode)."""
        try:
            secret_string = os.getenv(env_var_name)
            if secret_string:
                return json.loads(secret_string)
            return None
        except Exception as e:
            print(f"Error parsing {env_var_name} from environment: {e}")
            return None

    def get_redis_credentials(self, redis_name: str) -> dict:
        """
        Get Redis credentials for a specific instance.

        Args:
            redis_name: "redis-cache-1", "redis-cache-2", etc.

        Returns:
            dict with host, port, password, db
        """
        prefix = redis_name.upper().replace("-", "_")

        if self.use_aws_secrets:
            secret_arn = os.getenv(f"{prefix}_SECRET_ARN")
            if not secret_arn:
                print(f"Warning: {prefix}_SECRET_ARN not set")
                return {}
            creds = self.get_secret(secret_arn)
        else:
            # Testing: try env var with JSON
            env_var = f"{prefix}_CREDENTIALS"
            creds = self.get_secret(env_var)

        if not creds:
            # Fallback to individual env vars
            return {
                "host": os.getenv(f"{prefix}_HOST", "localhost"),
                "port": int(os.getenv(f"{prefix}_PORT", 6379)),
                "password": os.getenv(f"{prefix}_PASSWORD"),
                "db": int(os.getenv(f"{prefix}_DB", 0)),
            }
        return creds

    def get_database_credentials(self, db_name: str = "postgres") -> dict:
        """
        Get database credentials.

        Args:
            db_name: "postgres", "postgres-primary", etc.

        Returns:
            dict with host, port, username, password, database
        """
        prefix = db_name.upper().replace("-", "_")

        if self.use_aws_secrets:
            secret_arn = os.getenv(f"{prefix}_SECRET_ARN")
            if not secret_arn:
                print(f"Warning: {prefix}_SECRET_ARN not set")
                return {}
            creds = self.get_secret(secret_arn)
        else:
            # Testing: try env var with JSON
            env_var = f"{prefix}_CREDENTIALS"
            creds = self.get_secret(env_var)

        if not creds:
            # Fallback to individual env vars
            return {
                "host": os.getenv(f"{prefix}_HOST", "localhost"),
                "port": int(os.getenv(f"{prefix}_PORT", 5432)),
                "username": os.getenv(f"{prefix}_USERNAME", "monitoring_user"),
                "password": os.getenv(f"{prefix}_PASSWORD"),
                "database": os.getenv(f"{prefix}_DATABASE", "snitch_prod"),
            }
        return creds


# Singleton instance
_credentials_manager = None


def get_credentials_manager() -> CredentialsManager:
    """Get or create the credentials manager singleton."""
    global _credentials_manager
    if _credentials_manager is None:
        _credentials_manager = CredentialsManager()
    return _credentials_manager
