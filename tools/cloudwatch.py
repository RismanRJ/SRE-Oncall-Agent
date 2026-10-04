"""CloudWatch metrics: App Runner CPU/instance count, RDS CPU (read-only)."""
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import boto3


def _cw_client(region: str = None):
    region = region or os.getenv("AWS_REGION", "ap-south-1")
    return boto3.client("cloudwatch", region_name=region)


def get_apprunner_metrics(service_name: str, region: str = None, lookback_minutes: int = 30) -> Dict:
    """
    Fetch service-level CPU utilization and active instance count for an App Runner service.
    Uses the ServiceName+ServiceID aggregate dimension (not per-Instance, which CloudWatch
    keeps listing long after instances are recycled/terminated).
    """
    cw = _cw_client(region)
    end = datetime.utcnow()
    start = end - timedelta(minutes=lookback_minutes)

    # Discover ServiceID from any metric with this ServiceName
    metrics = cw.list_metrics(
        Namespace="AWS/AppRunner",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "ServiceName", "Value": service_name}],
    )["Metrics"]
    service_id = next(
        (d["Value"] for m in metrics for d in m["Dimensions"] if d["Name"] == "ServiceID"),
        None,
    )
    if not service_id:
        return {"cpu_percent": None, "instance_count": None}

    dimensions = [
        {"Name": "ServiceName", "Value": service_name},
        {"Name": "ServiceID", "Value": service_id},
    ]

    cpu_resp = cw.get_metric_statistics(
        Namespace="AWS/AppRunner",
        MetricName="CPUUtilization",
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average"],
    )
    cpu_datapoints = sorted(cpu_resp["Datapoints"], key=lambda d: d["Timestamp"])
    cpu_percent = round(cpu_datapoints[-1]["Average"], 2) if cpu_datapoints else None

    instances_resp = cw.get_metric_statistics(
        Namespace="AWS/AppRunner",
        MetricName="ActiveInstances",
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average"],
    )
    instance_datapoints = sorted(instances_resp["Datapoints"], key=lambda d: d["Timestamp"])
    instance_count = round(instance_datapoints[-1]["Average"]) if instance_datapoints else None

    return {
        "cpu_percent": cpu_percent,
        "instance_count": instance_count,
    }


def get_rds_cpu(db_instance_identifier: str, region: str = None, lookback_minutes: int = 15) -> Optional[float]:
    """Fetch latest CPU utilization for a specific RDS/Aurora instance (the writer)."""
    cw = _cw_client(region)
    end = datetime.utcnow()
    start = end - timedelta(minutes=lookback_minutes)

    resp = cw.get_metric_statistics(
        Namespace="AWS/RDS",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_instance_identifier}],
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average"],
    )
    datapoints = sorted(resp["Datapoints"], key=lambda d: d["Timestamp"])
    return round(datapoints[-1]["Average"], 2) if datapoints else None


def get_rds_cluster_members(cluster_identifier: str, region: str = None):
    """List instances (writer + readers) in an RDS/Aurora cluster with their role."""
    region = region or os.getenv("AWS_REGION", "ap-south-1")
    rds = boto3.client("rds", region_name=region)
    try:
        clusters = rds.describe_db_clusters(DBClusterIdentifier=cluster_identifier)["DBClusters"]
        if not clusters:
            return None
        return [
            {"identifier": m["DBInstanceIdentifier"], "is_writer": m["IsClusterWriter"]}
            for m in clusters[0]["DBClusterMembers"]
        ]
    except Exception as e:
        print(f"Error fetching RDS cluster info for {cluster_identifier}: {e}")
        return None
