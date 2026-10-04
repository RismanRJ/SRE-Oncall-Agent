import streamlit as st
import requests
from storage.incidents import list_incidents, get_incident
from auth.users import get_all_engineers
from datetime import datetime

# Page config
st.set_page_config(
    page_title="SRE Oncall Agent",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API base URL
API_URL = "http://localhost:8000"


def get_auth_header():
    """Get Authorization header with JWT token."""
    if "token" in st.session_state:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def login_page():
    """Login page."""
    st.title("🔐 SRE Oncall Agent - Login")

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.write("### Sign In")

            email = st.text_input("Email", placeholder="engineer@company.com")
            password = st.text_input("Password", type="password")

            if st.button("Login", use_container_width=True):
                if not email or not password:
                    st.error("Please enter email and password")
                else:
                    try:
                        response = requests.post(
                            f"{API_URL}/auth/login",
                            json={"email": email, "password": password},
                        )
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.token = data["token"]
                            st.session_state.email = data["email"]
                            st.session_state.name = data["name"]
                            st.session_state.role = data["role"]
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                    except Exception as e:
                        st.error(f"Connection error: {str(e)}")

            st.divider()
            st.caption("Demo Credentials:")
            st.caption("👤 alice@company.com / alice_secure_pass_123 (Admin)")
            st.caption("👤 bob@company.com / bob_secure_pass_456 (Engineer)")
            st.caption("👤 carol@company.com / carol_secure_pass_789 (Engineer)")


def home_page():
    """Home dashboard page with live metrics and health status."""
    st.header("📊 System Status Dashboard")

    # User info and controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.write(f"Welcome, **{st.session_state.name}** ({st.session_state.role})")
    with col2:
        refresh_clicked = st.button("🔄 Refresh Metrics", use_container_width=True)
    with col3:
        if st.button("🚪 Logout"):
            del st.session_state.token
            del st.session_state.email
            del st.session_state.name
            del st.session_state.role
            st.rerun()

    st.divider()

    # Get current on-call engineer
    try:
        oncall_response = requests.get(
            f"{API_URL}/oncall/engineer", headers=get_auth_header()
        )
        if oncall_response.status_code == 200:
            oncall = oncall_response.json()
            if "error" not in oncall:
                st.info(
                    f"🟢 **On-Call Engineer:** {oncall.get('name')} "
                    f"| Phone: {oncall.get('phone')} | Slack: {oncall.get('slack_id')}"
                )
    except Exception as e:
        st.warning(f"Could not load on-call info: {e}")

    st.divider()

    # Discover all configured services
    if "service_names" not in st.session_state:
        try:
            resp = requests.get(f"{API_URL}/services/list", headers=get_auth_header())
            st.session_state.service_names = resp.json().get("services", []) if resp.status_code == 200 else []
        except Exception as e:
            st.session_state.service_names = []
            st.warning(f"Could not load service list: {e}")

    service_names = st.session_state.service_names

    # Fetch metrics for all services on first load or refresh click
    if refresh_clicked or "services_metrics" not in st.session_state:
        services_metrics = {}
        with st.spinner(f"🔄 Fetching metrics for {len(service_names)} service(s)..."):
            for svc in service_names:
                try:
                    resp = requests.post(
                        f"{API_URL}/webhook/check",
                        json={"service": svc},
                        headers=get_auth_header(),
                    )
                    services_metrics[svc] = (
                        resp.json() if resp.status_code == 200 else {"status": "error", "message": f"HTTP {resp.status_code}"}
                    )
                except Exception as e:
                    services_metrics[svc] = {"status": "error", "message": str(e)}
        st.session_state.services_metrics = services_metrics
        if refresh_clicked:
            st.success(f"✅ Refreshed {len(service_names)} service(s)!")

    services_metrics = st.session_state.get("services_metrics", {})

    # Overall summary across all services
    total_critical = 0
    total_warning = 0
    for data in services_metrics.values():
        for b in data.get("breaches", []):
            if b.get("severity") == "critical":
                total_critical += 1
            elif b.get("severity") == "warning":
                total_warning += 1

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔴 Critical Breaches", total_critical)
    with col2:
        st.metric("🟡 Warning Breaches", total_warning)
    with col3:
        st.metric("📊 Services Monitored", len(services_metrics))

    st.divider()

    # Separate infrastructure vs app services
    infrastructure_services = {k: v for k, v in services_metrics.items() if any(x in k.lower() for x in ["redis", "postgres", "database", "elasticsearch", "aurora"])}
    app_services = {k: v for k, v in services_metrics.items() if k not in infrastructure_services}

    # Display Applications
    if app_services:
        st.subheader("🚀 Applications")
        for svc, metrics_data in sorted(app_services.items()):
            _render_service_card(svc, metrics_data)

    # Display Infrastructure
    if infrastructure_services:
        st.divider()
        st.subheader("🏗️ Infrastructure")
        for svc, metrics_data in sorted(infrastructure_services.items()):
            _render_service_card(svc, metrics_data, is_infrastructure=True)


def _render_service_card(svc: str, metrics_data: dict, is_infrastructure: bool = False):
    """Render a single service card with metrics and status."""
    status = metrics_data.get("status", "unknown")

    if status == "healthy":
        badge = "✅ Healthy"
    elif status == "breach_detected":
        severities = {b.get("severity") for b in metrics_data.get("breaches", [])}
        badge = "🔴 Critical" if "critical" in severities else "🟡 Warning"
    else:
        badge = "⚠️ Error"

    with st.expander(f"{badge} — **{svc}**"):
        if status == "error":
            st.error(metrics_data.get("message", "Unknown error"))
            return

        metrics = metrics_data.get("metrics", {})

        if is_infrastructure:
            # For infrastructure services with single source, simplify display
            enabled_sources = [k for k, v in metrics.items() if isinstance(v, dict) and v and not v.get("error")]
            if len(enabled_sources) == 1:
                source_key = enabled_sources[0]
                source_data = metrics[source_key]
                _render_metric_section(source_key, source_data, full_width=True)
            else:
                col1, col2, col3, col4 = st.columns(4)
                sources = {
                    "database": ("Database", col1),
                    "redis": ("Redis", col2),
                    "elasticsearch": ("Elasticsearch", col3),
                    "aws": ("AWS (CPU)", col4),
                }
                for source_key, (source_name, col) in sources.items():
                    source_data = metrics.get(source_key)
                    with col:
                        _render_metric_section(source_key, source_data, source_name=source_name)
        else:
            # App services: single compact row - TP99, Error Rate, Throughput, CPU, Instances
            nr = metrics.get("newrelic") or {}
            aws = metrics.get("aws") or {}
            tp99 = nr.get("tp99_ms")
            error_rate = nr.get("error_rate_percent")
            throughput = nr.get("throughput_rpm_min")
            cpu = aws.get("cpu_percent")
            instances = aws.get("instance_count")

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("TP99", f"{tp99:.0f}ms" if tp99 is not None else "N/A")
            with col2:
                st.metric("Error Rate", f"{error_rate:.2f}%" if error_rate is not None else "N/A")
            with col3:
                st.metric("Throughput", f"{throughput:.0f} RPM" if throughput is not None else "N/A")
            with col4:
                st.metric("CPU", f"{cpu:.0f}%" if cpu is not None else "N/A")
            with col5:
                st.metric("Instances", f"{instances}" if instances is not None else "N/A")

            st.divider()

            # Top slow transactions (lazy-loaded)
            cache_key = f"slow_txns_{svc}"
            if st.button("🔍 Show Top Slow Transactions", key=f"btn_{svc}"):
                try:
                    resp = requests.get(
                        f"{API_URL}/services/{svc}/slow-transactions?limit=10",
                        headers=get_auth_header(),
                    )
                    st.session_state[cache_key] = (
                        resp.json().get("transactions", []) if resp.status_code == 200 else []
                    )
                except Exception as e:
                    st.session_state[cache_key] = []
                    st.warning(f"Could not load slow transactions: {e}")

            if cache_key in st.session_state:
                transactions = st.session_state[cache_key]
                if transactions:
                    st.write("**Top Slow Transactions (last 60 min):**")
                    for t in transactions:
                        name = t.get("name", "unknown")
                        tp95 = t.get("tp95_ms")
                        tp99_t = t.get("tp99_ms")
                        count = t.get("request_count")
                        st.caption(
                            f"`{name}` — TP95: {tp95:.0f}ms | TP99: {tp99_t:.0f}ms | {count} req"
                            if tp95 is not None and tp99_t is not None
                            else f"`{name}` — no data"
                        )
                else:
                    st.caption("No transaction data available")

        # Display breaches
        if status == "breach_detected":
            st.divider()
            st.write("**⚠️ Breaches:**")
            for breach in metrics_data.get("breaches", []):
                severity = breach.get("severity", "unknown")
                message = breach.get("message", "")
                if severity == "critical":
                    st.error(f"🔴 {message}")
                else:
                    st.warning(f"🟡 {message}")


def _render_metric_section(source_key: str, source_data: dict, source_name: str = None, full_width: bool = False):
    """Render metrics for a specific source."""
    if not source_name:
        source_map = {
            "newrelic": "New Relic",
            "database": "Database",
            "redis": "Redis",
            "elasticsearch": "Elasticsearch",
            "aws": "AWS",
        }
        source_name = source_map.get(source_key, source_key)

    if not source_data:
        st.write(f"⏸️ **{source_name}**")
        st.caption("Not configured")
        return

    if source_data.get("error"):
        st.write(f"⚠️ **{source_name}**")
        st.caption(f"Error: {str(source_data.get('error', 'Unknown'))[:50]}")
        return

    if any(v is not None for v in source_data.values() if not isinstance(v, list)):
        st.write(f"✅ **{source_name}**")

        if source_key == "newrelic":
            tp99 = source_data.get("tp99_ms")
            error_rate = source_data.get("error_rate_percent")
            throughput = source_data.get("throughput_rpm_min")
            col1, col2, col3 = st.columns(3) if full_width else (None, None, None)
            if full_width:
                with col1:
                    st.metric("TP99 Latency", f"{tp99:.0f}ms" if tp99 is not None else "N/A")
                with col2:
                    st.metric("Error Rate", f"{error_rate:.2f}%" if error_rate is not None else "N/A")
                with col3:
                    st.metric("Throughput", f"{throughput:.0f} RPM" if throughput is not None else "N/A")
            else:
                st.metric("TP99", f"{tp99:.0f}ms" if tp99 is not None else "N/A")
                st.metric("Error Rate", f"{error_rate:.2f}%" if error_rate is not None else "N/A")
                st.metric("Throughput", f"{throughput:.0f} RPM" if throughput is not None else "N/A")

        elif source_key == "database":
            conn_pct = source_data.get("active_connections_percent")
            slow_q = source_data.get("slow_query_count")
            total_conn = source_data.get("total_connections")
            max_conn = source_data.get("max_connections")
            active_conn = source_data.get("active_connections")
            idle_conn = source_data.get("idle_connections")
            idle_tx = source_data.get("idle_in_transaction")
            cache_hit = source_data.get("cache_hit_ratio")
            cpu = source_data.get("cpu_percent")
            instances = source_data.get("instance_count")
            readers = source_data.get("readers") or []

            if full_width:
                st.caption("Writer instance")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Connections", f"{total_conn}" if total_conn is not None else "N/A",
                               help=f"of {max_conn} max" if max_conn is not None else None)
                with col2:
                    st.metric("Active", f"{active_conn}" if active_conn is not None else "N/A")
                with col3:
                    st.metric("Idle", f"{idle_conn}" if idle_conn is not None else "N/A")
                with col4:
                    st.metric("Idle in TX", f"{idle_tx}" if idle_tx is not None else "N/A")

                col5, col6, col7, col8 = st.columns(4)
                with col5:
                    st.metric("Max Connections", f"{max_conn}" if max_conn is not None else "N/A")
                with col6:
                    st.metric("Slow Queries", f"{slow_q}" if slow_q is not None else "N/A")
                with col7:
                    st.metric("Cache Hit", f"{cache_hit:.1%}" if cache_hit is not None else "N/A")
                with col8:
                    st.metric("Writer CPU", f"{cpu:.0f}%" if cpu is not None else "N/A")

                st.metric("Cluster Instances", f"{instances}" if instances is not None else "N/A")

                if readers:
                    st.caption("Reader instances")
                    reader_cols = st.columns(len(readers))
                    for col, r in zip(reader_cols, readers):
                        with col:
                            rcpu = r.get("cpu_percent")
                            st.metric(r["identifier"], f"{rcpu:.0f}% CPU" if rcpu is not None else "N/A")
            else:
                st.metric("Connections", f"{conn_pct:.0f}%" if conn_pct is not None else "N/A",
                           help=f"{total_conn}/{max_conn}" if total_conn is not None and max_conn is not None else None)
                st.metric("Slow Queries", f"{slow_q}" if slow_q is not None else "N/A")
                st.metric("CPU", f"{cpu:.0f}%" if cpu is not None else "N/A")

        elif source_key == "redis":
            mem = source_data.get("memory_percent")
            hit_rate = source_data.get("hit_rate")
            connected = source_data.get("connected_clients")
            commands = source_data.get("commands_per_sec")

            if full_width:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Memory", f"{mem:.0f}%" if mem is not None else "N/A")
                with col2:
                    st.metric("Hit Rate", f"{hit_rate:.1%}" if hit_rate is not None else "N/A")
                with col3:
                    st.metric("Clients", f"{connected:.0f}" if connected is not None else "N/A")
                with col4:
                    st.metric("Cmds/sec", f"{commands:.0f}" if commands is not None else "N/A")
            else:
                st.metric("Memory", f"{mem:.0f}%" if mem is not None else "N/A")
                st.metric("Hit Rate", f"{hit_rate:.1%}" if hit_rate is not None else "N/A")

        elif source_key == "aws":
            cpu = source_data.get("cpu_percent")
            instances = source_data.get("instance_count")
            if full_width:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("CPU", f"{cpu:.0f}%" if cpu is not None else "N/A")
                with col2:
                    st.metric("Instances", f"{instances}" if instances is not None else "N/A")
            else:
                st.metric("CPU", f"{cpu:.0f}%" if cpu is not None else "N/A")
                st.metric("Instances", f"{instances}" if instances is not None else "N/A")

        elif source_key == "elasticsearch":
            es_status = source_data.get("cluster_status")
            unassigned = source_data.get("unassigned_shards")
            if full_width:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Status", es_status if es_status else "N/A")
                with col2:
                    st.metric("Unassigned", f"{unassigned:.0f}" if unassigned is not None else "N/A")
            else:
                st.metric("Status", es_status if es_status else "N/A")
                st.metric("Unassigned", f"{unassigned:.0f}" if unassigned is not None else "N/A")
    else:
        st.write(f"⏸️ **{source_name}**")
        st.caption("No data")

    st.divider()


def incidents_page():
    """Incident history page."""
    st.header("📋 Incident History")

    # Get all incidents
    all_incidents = list_incidents(limit=50)

    if all_incidents:
        # Create a table view
        incident_list = []
        for inc in all_incidents:
            engineer = inc.get("oncall_engineer") or {}
            incident_list.append(
                {
                    "ID": inc.get("incident_id"),
                    "Service": inc.get("service"),
                    "Severity": inc.get("severity"),
                    "Metric": inc.get("breach_metric"),
                    "Value": f"{inc.get('breach_value', 0):.1f}",
                    "Engineer": engineer.get("name", "Unknown"),
                    "Timestamp": inc.get("timestamp"),
                }
            )

        st.dataframe(incident_list, use_container_width=True)

        st.divider()
        st.subheader("Incident Details")

        # Select incident to view
        incident_ids = [inc.get("incident_id") for inc in all_incidents]
        selected_id = st.selectbox("Select Incident", options=incident_ids)

        if selected_id:
            incident = next(
                (inc for inc in all_incidents if inc.get("incident_id") == selected_id),
                None,
            )
            if incident:
                engineer = incident.get("oncall_engineer") or {}
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** {incident.get('incident_id')}")
                    st.write(f"**Service:** {incident.get('service')}")
                    st.write(f"**Severity:** {incident.get('severity')}")
                    st.write(f"**Timestamp:** {incident.get('timestamp')}")
                with col2:
                    st.write(f"**Metric:** {incident.get('breach_metric')}")
                    st.write(f"**Value:** {incident.get('breach_value')}")
                    st.write(
                        f"**Engineer Notified:** {engineer.get('name')} ({engineer.get('phone')})"
                    )

                st.write(f"**Root Cause:** {incident.get('root_cause')}")

                st.write("**Evidence:**")
                for evidence in incident.get("evidence", []):
                    st.write(f"- {evidence}")

                st.write(f"**Suggestion:** {incident.get('suggestion')}")
    else:
        st.info("No incidents found")


def admin_panel():
    """Admin panel for managing on-call schedule."""
    if st.session_state.role != "admin":
        st.error("❌ Admin access only")
        return

    st.header("⚙️ Admin Panel - On-Call Schedule")

    # Get all engineers
    engineers = get_all_engineers()
    engineer_options = {eng["name"]: eng["email"] for eng in engineers}

    # Tabs for different views
    tab1, tab2 = st.tabs(["📅 Add/Edit Rotation", "📋 View Rotations"])

    with tab1:
        st.subheader("Add New On-Call Rotation")

        col1, col2, col3 = st.columns(3)

        with col1:
            start_date = st.date_input("Start Date", key="start_date")

        with col2:
            end_date = st.date_input("End Date", key="end_date")

        with col3:
            selected_engineer = st.selectbox(
                "Select Engineer",
                options=list(engineer_options.keys()),
                key="select_engineer",
            )

        if st.button("➕ Add Rotation", use_container_width=True):
            if start_date > end_date:
                st.error("❌ Start date must be before end date")
            else:
                try:
                    from oncall.schedule import add_rotation

                    engineer_email = engineer_options[selected_engineer]
                    if add_rotation(
                        start_date.isoformat(),
                        end_date.isoformat(),
                        engineer_email,
                    ):
                        st.success(
                            f"✓ Added rotation: {selected_engineer} ({start_date} to {end_date})"
                        )
                        st.rerun()
                    else:
                        st.error("Failed to add rotation")
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab2:
        st.subheader("Current Rotations")

        try:
            from oncall.schedule import get_all_rotations, delete_rotation

            rotations = get_all_rotations()

            if rotations:
                # Display as table
                for idx, rotation in enumerate(rotations):
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

                    with col1:
                        st.write(f"**{rotation['start_date']}**")

                    with col2:
                        st.write(f"**{rotation['end_date']}**")

                    with col3:
                        st.write(f"**{rotation['engineer_name']}**")

                    with col4:
                        if st.button(
                            "🗑️",
                            key=f"delete_{idx}",
                            help="Delete this rotation",
                        ):
                            if delete_rotation(
                                rotation["start_date"], rotation["end_date"]
                            ):
                                st.success("✓ Rotation deleted")
                                st.rerun()
                            else:
                                st.error("Failed to delete rotation")

                st.divider()

                # Show next 7 days schedule
                st.subheader("Next 7 Days Schedule")
                from datetime import datetime, timedelta

                today = datetime.utcnow().date()
                for i in range(7):
                    date = today + timedelta(days=i)
                    from oncall.schedule import get_oncall_engineer

                    engineer = get_oncall_engineer(date)
                    day_name = date.strftime("%A")
                    engineer_name = (
                        engineer.get("name") if engineer else "Unassigned"
                    )
                    st.write(f"**{day_name} ({date})**: {engineer_name}")
            else:
                st.info("No rotations scheduled yet")

        except Exception as e:
            st.error(f"Error loading rotations: {e}")


# Main app logic
if "token" not in st.session_state:
    login_page()
else:
    # User is logged in
    page = st.sidebar.radio(
        "Navigation",
        options=["Home", "Incidents", "Admin"] if st.session_state.role == "admin" else ["Home", "Incidents"],
        index=0,
    )

    if page == "Home":
        home_page()
    elif page == "Incidents":
        incidents_page()
    elif page == "Admin":
        admin_panel()
