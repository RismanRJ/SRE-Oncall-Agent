from typing import Optional, List
from .schema import Breach


def evaluate(service_config: dict, metrics: dict) -> List[Breach]:
    """
    Evaluate ALL metrics against service thresholds.
    Returns list of all breaches found (empty if none).

    Args:
        service_config: Service configuration with thresholds
        metrics: All metrics dict from metrics.fetcher (with keys: newrelic, database, redis, elasticsearch)

    Returns:
        List of Breach objects (empty if no thresholds exceeded)
    """
    breaches = []
    thresholds = service_config.get("thresholds", {})
    severity_rules = service_config.get("severity", {})

    # Check New Relic metrics
    if metrics.get("newrelic"):
        nr_breaches = _check_newrelic_thresholds(
            metrics["newrelic"],
            thresholds.get("newrelic", {}),
            severity_rules
        )
        breaches.extend(nr_breaches)

    # Check Database metrics
    if metrics.get("database"):
        db_breaches = _check_database_thresholds(
            metrics["database"],
            thresholds.get("database", {}),
            severity_rules
        )
        breaches.extend(db_breaches)

    # Check Redis metrics
    if metrics.get("redis"):
        redis_breaches = _check_redis_thresholds(
            metrics["redis"],
            thresholds.get("redis", {}),
            severity_rules
        )
        breaches.extend(redis_breaches)

    # Check Elasticsearch metrics
    if metrics.get("elasticsearch"):
        es_breaches = _check_elasticsearch_thresholds(
            metrics["elasticsearch"],
            thresholds.get("elasticsearch", {}),
            severity_rules
        )
        breaches.extend(es_breaches)

    return breaches


def _check_newrelic_thresholds(metrics: dict, thresholds: dict, severity_rules: dict) -> List[Breach]:
    """Check New Relic metrics against thresholds."""
    breaches = []

    if not metrics:
        return breaches

    critical_rules = severity_rules.get("critical", {}).get("newrelic", [])
    warning_rules = severity_rules.get("warning", {}).get("newrelic", [])

    # Check TP99 latency
    tp99_actual = metrics.get("tp99_ms")
    tp99_threshold = thresholds.get("tp99_ms")
    if tp99_threshold is not None and tp99_actual is not None and tp99_actual > tp99_threshold:
        severity = "critical" if tp99_actual > 3000 else "warning"
        breaches.append(Breach(
            metric_name="tp99_latency_ms",
            metric_value=tp99_actual,
            threshold=tp99_threshold,
            severity=severity,
            message=f"TP99 latency {tp99_actual}ms exceeds {tp99_threshold}ms threshold",
        ))

    # Check TP95 latency
    tp95_actual = metrics.get("tp95_ms")
    tp95_threshold = thresholds.get("tp95_ms")
    if tp95_threshold is not None and tp95_actual is not None and tp95_actual > tp95_threshold:
        severity = "warning"
        breaches.append(Breach(
            metric_name="tp95_latency_ms",
            metric_value=tp95_actual,
            threshold=tp95_threshold,
            severity=severity,
            message=f"TP95 latency {tp95_actual}ms exceeds {tp95_threshold}ms threshold",
        ))

    # Check error rate
    error_actual = metrics.get("error_rate_percent")
    error_threshold = thresholds.get("error_rate_percent")
    if error_threshold is not None and error_actual is not None and error_actual > error_threshold:
        severity = "critical" if error_actual > 10 else "warning"
        breaches.append(Breach(
            metric_name="error_rate_percent",
            metric_value=error_actual,
            threshold=error_threshold,
            severity=severity,
            message=f"Error rate {error_actual}% exceeds {error_threshold}% threshold",
        ))

    # Check throughput (min RPM)
    throughput_actual = metrics.get("throughput_rpm_min")
    throughput_threshold = thresholds.get("throughput_rpm_min")
    if throughput_threshold is not None and throughput_actual is not None and throughput_actual < throughput_threshold:
        severity = "critical" if throughput_actual < 5 else "warning"
        breaches.append(Breach(
            metric_name="throughput_rpm_min",
            metric_value=throughput_actual,
            threshold=throughput_threshold,
            severity=severity,
            message=f"Throughput {throughput_actual} RPM below {throughput_threshold} RPM threshold",
        ))

    return breaches


def _check_database_thresholds(metrics: dict, thresholds: dict, severity_rules: dict) -> List[Breach]:
    """Check Database metrics against thresholds."""
    breaches = []

    if not metrics:
        return breaches

    # Check connection percentage
    conn_pct = metrics.get("active_connections_percent")
    conn_threshold = thresholds.get("active_connections_percent")
    if conn_threshold is not None and conn_pct is not None and conn_pct > conn_threshold:
        severity = "critical" if conn_pct > 90 else "warning"
        breaches.append(Breach(
            metric_name="database_active_connections_percent",
            metric_value=conn_pct,
            threshold=conn_threshold,
            severity=severity,
            message=f"Database connections at {conn_pct}% exceeds {conn_threshold}% threshold",
        ))

    # Check slow query count
    slow_queries = metrics.get("slow_query_count", 0)
    slow_threshold = thresholds.get("slow_query_count")
    if slow_threshold is not None and slow_queries > slow_threshold:
        severity = "critical" if slow_queries > 20 else "warning"
        breaches.append(Breach(
            metric_name="database_slow_query_count",
            metric_value=slow_queries,
            threshold=slow_threshold,
            severity=severity,
            message=f"Slow queries {slow_queries} exceeds {slow_threshold} threshold",
        ))

    # Check connection wait time
    wait_ms = metrics.get("connection_wait_ms", 0)
    wait_threshold = thresholds.get("connection_wait_ms")
    if wait_threshold is not None and wait_ms > wait_threshold:
        severity = "warning"
        breaches.append(Breach(
            metric_name="database_connection_wait_ms",
            metric_value=wait_ms,
            threshold=wait_threshold,
            severity=severity,
            message=f"Connection wait time {wait_ms}ms exceeds {wait_threshold}ms threshold",
        ))

    return breaches


def _check_redis_thresholds(metrics: dict, thresholds: dict, severity_rules: dict) -> List[Breach]:
    """Check Redis metrics against thresholds."""
    breaches = []

    if not metrics:
        return breaches

    # Check memory percentage
    mem_pct = metrics.get("memory_percent")
    mem_threshold = thresholds.get("memory_percent")
    if mem_threshold is not None and mem_pct is not None and mem_pct > mem_threshold:
        severity = "critical" if mem_pct > 95 else "warning"
        breaches.append(Breach(
            metric_name="redis_memory_percent",
            metric_value=mem_pct,
            threshold=mem_threshold,
            severity=severity,
            message=f"Redis memory at {mem_pct}% exceeds {mem_threshold}% threshold",
        ))

    # Check eviction rate
    evictions = metrics.get("eviction_rate")
    eviction_threshold = thresholds.get("eviction_rate")
    if eviction_threshold is not None and evictions is not None and evictions > eviction_threshold:
        severity = "warning"
        breaches.append(Breach(
            metric_name="redis_eviction_rate",
            metric_value=evictions,
            threshold=eviction_threshold,
            severity=severity,
            message=f"Redis evictions {evictions}/min exceeds {eviction_threshold}/min threshold",
        ))

    return breaches


def _check_elasticsearch_thresholds(metrics: dict, thresholds: dict, severity_rules: dict) -> List[Breach]:
    """Check Elasticsearch metrics against thresholds."""
    breaches = []

    if not metrics:
        return breaches

    # Check cluster status
    cluster_status = metrics.get("cluster_status", "red")
    expected_status = thresholds.get("cluster_status", "green")
    if cluster_status != expected_status:
        severity = "critical"
        breaches.append(Breach(
            metric_name="elasticsearch_cluster_status",
            metric_value=cluster_status,
            threshold=expected_status,
            severity=severity,
            message=f"Elasticsearch cluster status is {cluster_status}, expected {expected_status}",
        ))

    # Check unassigned shards
    unassigned = metrics.get("unassigned_shards", 0)
    unassigned_threshold = thresholds.get("unassigned_shards_max", 0)
    if unassigned > unassigned_threshold:
        severity = "critical" if unassigned > 0 else "warning"
        breaches.append(Breach(
            metric_name="elasticsearch_unassigned_shards",
            metric_value=unassigned,
            threshold=unassigned_threshold,
            severity=severity,
            message=f"Elasticsearch has {unassigned} unassigned shards",
        ))

    # Check JVM memory
    jvm_pct = metrics.get("jvm_memory_percent")
    jvm_threshold = thresholds.get("jvm_memory_percent")
    if jvm_threshold is not None and jvm_pct is not None and jvm_pct > jvm_threshold:
        severity = "warning"
        breaches.append(Breach(
            metric_name="elasticsearch_jvm_memory_percent",
            metric_value=jvm_pct,
            threshold=jvm_threshold,
            severity=severity,
            message=f"Elasticsearch JVM memory at {jvm_pct}% exceeds {jvm_threshold}% threshold",
        ))

    return breaches
