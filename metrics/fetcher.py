"""
Unified metrics fetcher that pulls from all configured data sources.
Fetches New Relic, Database, Redis, Elasticsearch metrics based on service config.
"""
from datetime import datetime
from tools.newrelic import get_service_metrics as get_nr_metrics
from tools.database import get_database_metrics
from tools.redis import get_redis_metrics
from tools.elasticsearch import get_elasticsearch_metrics
from tools.cloudwatch import get_apprunner_metrics


def fetch_all_metrics(service_config: dict, app_name: str = None) -> dict:
    """
    Fetch all configured metrics for a service synchronously.

    Args:
        service_config: Service configuration from YAML
        app_name: New Relic app name (overrides config if provided)

    Returns:
        dict with metrics organized by source (newrelic, database, redis, elasticsearch)
    """
    metrics_config = service_config.get("metrics", {})
    results = {
        "newrelic": None,
        "database": None,
        "redis": None,
        "elasticsearch": None,
        "aws": None,
        "timestamp": None,
    }

    # Fetch New Relic metrics
    if metrics_config.get("newrelic"):
        try:
            nr_config = service_config.get("newrelic", {})
            app = app_name or nr_config.get("app_name")
            lookback_minutes = nr_config.get("lookback_minutes", 5)
            errors_lookback_minutes = nr_config.get("errors_lookback_minutes", 30)
            if app:
                results["newrelic"] = get_nr_metrics(app, lookback_minutes, errors_lookback_minutes)
        except Exception as e:
            print(f"New Relic fetch failed: {e}")
            results["newrelic"] = {"error": str(e)}

    # Fetch database metrics
    if metrics_config.get("database"):
        try:
            db_config = service_config.get("database", {})
            # Add service name for credentials lookup
            service_name = service_config.get("service", {}).get("name")
            if service_name and "name" not in db_config:
                db_config["name"] = service_name
            # Pass through top-level aws config for CPU/instance count
            if service_config.get("aws") and "aws" not in db_config:
                db_config["aws"] = service_config["aws"]
            results["database"] = get_database_metrics(db_config)
        except Exception as e:
            print(f"Database fetch failed: {e}")
            results["database"] = {"error": str(e)}

    # Fetch Redis metrics
    if metrics_config.get("redis"):
        try:
            redis_config = service_config.get("redis", {})
            # Convert null password to None
            if redis_config.get("password") == "null" or redis_config.get("password") is None:
                redis_config["password"] = None
            # Add service name for credentials lookup
            service_name = service_config.get("service", {}).get("name")
            if service_name and "redis" in service_name.lower():
                redis_config["name"] = service_name
            results["redis"] = get_redis_metrics(redis_config)
        except Exception as e:
            print(f"Redis fetch failed: {e}")
            results["redis"] = {"error": str(e)}

    # Fetch Elasticsearch metrics
    if metrics_config.get("elasticsearch"):
        try:
            es_config = service_config.get("elasticsearch", {})
            results["elasticsearch"] = get_elasticsearch_metrics(es_config)
        except Exception as e:
            print(f"Elasticsearch fetch failed: {e}")
            results["elasticsearch"] = {"error": str(e)}

    # Fetch App Runner CPU/instance count from CloudWatch
    aws_config = service_config.get("aws")
    if aws_config and aws_config.get("apprunner_service_name"):
        try:
            results["aws"] = get_apprunner_metrics(
                aws_config["apprunner_service_name"],
                region=aws_config.get("region"),
            )
        except Exception as e:
            print(f"CloudWatch App Runner fetch failed: {e}")
            results["aws"] = {"error": str(e)}

    results["timestamp"] = datetime.utcnow().isoformat()
    return results


# Alias for backward compatibility
fetch_all_metrics_sync = fetch_all_metrics
