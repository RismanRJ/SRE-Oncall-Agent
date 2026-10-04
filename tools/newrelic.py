"""
New Relic Insights API client for fetching metrics via NRQL queries.
Uses the same Insights API approach as the Node.js reference implementation.
"""
import os
import httpx
from typing import Optional, Dict


class NewRelicClient:
    """New Relic Insights API client for fetching metrics via NRQL queries."""

    def __init__(self):
        self.api_key = os.getenv("NEW_RELIC_API_KEY")
        self.account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")

        # Use Insights API endpoint (same as Node.js reference)
        self.base_url = "https://insights-api.newrelic.com/v1"
        self.query_url = f"{self.base_url}/accounts/{self.account_id}/query"
        self.events_url = f"{self.base_url}/accounts/{self.account_id}/events"

        if not self.api_key or not self.account_id:
            raise ValueError(
                "NEW_RELIC_API_KEY and NEW_RELIC_ACCOUNT_ID environment variables required"
            )

    def _execute_nrql(self, nrql: str) -> dict:
        """Execute NRQL query via Insights API and return results."""
        headers = {
            "X-Query-Key": self.api_key,
            "Content-Type": "application/json",
        }

        params = {"nrql": nrql}

        try:
            response = httpx.get(
                self.query_url,
                params=params,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            # Handle API response
            if not data.get("results"):
                return {}

            # Return first result row
            return data["results"][0] if data["results"] else {}
        except httpx.HTTPError as e:
            raise Exception(f"New Relic API request failed: {str(e)}")

    def _execute_nrql_facets(self, nrql: str) -> list:
        """Execute a FACET NRQL query via Insights API and return the facets list."""
        headers = {
            "X-Query-Key": self.api_key,
            "Content-Type": "application/json",
        }
        params = {"nrql": nrql}

        try:
            response = httpx.get(
                self.query_url,
                params=params,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("facets", [])
        except httpx.HTTPError as e:
            raise Exception(f"New Relic API request failed: {str(e)}")

    @staticmethod
    def _extract_value(result: dict) -> Optional[float]:
        """
        Extract the single numeric value from an Insights API result row.
        The API ignores `as alias` for non-FACET queries and instead uses
        its own key (e.g. "result", "count", "average"), so we just grab
        the first (and only) value in the row.
        """
        if not result:
            return None
        for value in result.values():
            if isinstance(value, (int, float)):
                return float(value)
        return None

    def get_service_latency(self, app_name: str, lookback_minutes: int = 5) -> Optional[float]:
        """
        Get TP99 latency for a service.
        Returns latency in milliseconds, or None if unavailable.
        """
        nrql = f"SELECT percentile(duration, 99) * 1000 FROM Transaction WHERE appName = '{app_name}' SINCE {lookback_minutes} minutes ago"

        try:
            result = self._execute_nrql(nrql)
            return self._extract_value(result)
        except Exception as e:
            print(f"Error fetching latency for {app_name}: {e}")
            return None

    def get_error_rate(self, app_name: str, lookback_minutes: int = 5) -> Optional[float]:
        """
        Get error rate percentage for a service.
        Returns error rate as percentage, or None if unavailable.
        """
        nrql = f"SELECT (filter(count(*), WHERE error is true) / count(*)) * 100 FROM Transaction WHERE appName = '{app_name}' SINCE {lookback_minutes} minutes ago"

        try:
            result = self._execute_nrql(nrql)
            return self._extract_value(result)
        except Exception as e:
            print(f"Error fetching error rate for {app_name}: {e}")
            return None

    def get_throughput(self, app_name: str, lookback_minutes: int = 5) -> Optional[float]:
        """
        Get requests per minute (throughput) for a service.
        Returns RPM, or None if unavailable.
        """
        nrql = f"SELECT rate(count(*), 1 minute) FROM Transaction WHERE appName = '{app_name}' AND transactionType = 'Web' SINCE {lookback_minutes} minutes ago"

        try:
            result = self._execute_nrql(nrql)
            return self._extract_value(result)
        except Exception as e:
            print(f"Error fetching throughput for {app_name}: {e}")
            return None

    def get_slow_transactions(self, app_name: str, limit: int = 10, lookback_minutes: int = 60) -> list:
        """
        Get top slowest transactions by TP99 for a service, with DB/external time breakdown
        so the bottleneck can be attributed to a layer (database, external call, or app code).
        Returns list of {name, request_count, tp95_ms, tp99_ms, db_time_ms, external_time_ms, bottleneck},
        slowest first.
        """
        nrql = (
            f"SELECT count(*), percentile(duration, 95) * 1000, percentile(duration, 99) * 1000, "
            f"average(databaseDuration) * 1000, average(externalDuration) * 1000 "
            f"FROM Transaction WHERE appName = '{app_name}' "
            f"SINCE {lookback_minutes} minutes ago "
            f"FACET name LIMIT 50"
        )

        try:
            facets = self._execute_nrql_facets(nrql)
            transactions = []
            for facet in facets:
                name = facet.get("name", "unknown")
                results = facet.get("results", [])
                request_count = results[0].get("count") if len(results) > 0 else None
                tp95 = results[1].get("result") if len(results) > 1 else None
                tp99 = results[2].get("result") if len(results) > 2 else None
                db_time = results[3].get("result") if len(results) > 3 else None
                external_time = results[4].get("result") if len(results) > 4 else None

                if tp99 is None:
                    continue

                bottleneck = "application"
                if db_time is not None and tp99 and db_time > tp99 * 0.4:
                    bottleneck = "database"
                elif external_time is not None and tp99 and external_time > tp99 * 0.4:
                    bottleneck = "external_call"

                transactions.append({
                    "name": name,
                    "request_count": request_count,
                    "tp95_ms": tp95,
                    "tp99_ms": tp99,
                    "db_time_ms": db_time,
                    "external_time_ms": external_time,
                    "bottleneck": bottleneck,
                })
            transactions.sort(key=lambda t: t["tp99_ms"], reverse=True)
            return transactions[:limit]
        except Exception as e:
            print(f"Error fetching slow transactions for {app_name}: {e}")
            return []

    def get_recent_errors(self, app_name: str, lookback_minutes: int = 30) -> list:
        """
        Get recent error count for a service.
        Returns list with error count, or empty list if none.
        """
        nrql = f"SELECT count(*) FROM Transaction WHERE appName = '{app_name}' AND error is true SINCE {lookback_minutes} minutes ago"

        try:
            result = self._execute_nrql(nrql)
            count = self._extract_value(result)
            return [{"error_count": count}] if count is not None else []
        except Exception as e:
            print(f"Error fetching recent errors for {app_name}: {e}")
            return []


def get_service_metrics(app_name: str, lookback_minutes: int = 5, errors_lookback_minutes: int = 30) -> Dict:
    """
    Convenience function to fetch all metrics for a service.
    Returns dict with tp99_ms, error_rate_percent, throughput_rpm_min, etc.
    Uses Insights API (X-Query-Key header) like the Node.js reference.

    Args:
        app_name: New Relic APM app name.
        lookback_minutes: Time window for latency/error-rate/throughput queries.
        errors_lookback_minutes: Time window for the recent error count query.
    """
    try:
        client = NewRelicClient()
        return {
            "tp99_ms": client.get_service_latency(app_name, lookback_minutes),
            "error_rate_percent": client.get_error_rate(app_name, lookback_minutes),
            "throughput_rpm_min": client.get_throughput(app_name, lookback_minutes),
            "recent_errors": client.get_recent_errors(app_name, errors_lookback_minutes),
        }
    except Exception as e:
        print(f"Error initializing New Relic client: {e}")
        return {
            "tp99_ms": None,
            "error_rate_percent": None,
            "throughput_rpm_min": None,
            "recent_errors": [],
        }
