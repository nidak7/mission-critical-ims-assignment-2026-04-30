from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any


SEVERITY_CLASSES = {
    "P0": "sev-p0",
    "P1": "sev-p1",
    "P2": "sev-p2",
    "P3": "sev-p3",
}


def format_ts(value: str | None) -> str:
    if not value:
        return "n/a"
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def format_dt_input(value: str | None) -> str:
    if not value:
        return ""
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "Pending"
    minutes = int(seconds // 60)
    hours = minutes // 60
    remainder = minutes % 60
    if hours:
        return f"{hours}h {remainder}m"
    return f"{remainder}m"


def render_overview(health: dict[str, Any], incidents: list[dict[str, Any]]) -> str:
    p0_count = sum(1 for item in incidents if item["severity"] == "P0")
    return f"""
    <div class="metrics-grid">
      <section class="metric-card">
        <span class="metric-label">Queue depth</span>
        <strong class="metric-value">{health["queue_depth"]}</strong>
      </section>
      <section class="metric-card">
        <span class="metric-label">Signals / sec</span>
        <strong class="metric-value">{health["throughput_per_second"]:.2f}</strong>
      </section>
      <section class="metric-card">
        <span class="metric-label">Active incidents</span>
        <strong class="metric-value">{len(incidents)}</strong>
      </section>
      <section class="metric-card">
        <span class="metric-label">P0 incidents</span>
        <strong class="metric-value">{p0_count}</strong>
      </section>
    </div>
    """


def render_incident_feed(incidents: list[dict[str, Any]]) -> str:
    if not incidents:
        return """
        <div class="empty-state">
          <div>
            <h3>No active incidents</h3>
            <p>Run the sample scenario or post signals to <code>/api/signals</code>.</p>
          </div>
        </div>
        """

    rows = []
    for incident in incidents:
        severity_class = SEVERITY_CLASSES[incident["severity"]]
        rows.append(
            f"""
            <button
              class="incident-row {severity_class}"
              hx-get="/ui/incidents/{incident["id"]}"
              hx-target="#detail-panel"
              hx-swap="innerHTML"
            >
              <span class="kicker">{incident["severity"]} / {escape(incident["component_type"])}</span>
              <strong>{escape(incident["component_id"])}</strong>
              <p>{escape(incident["title"])}</p>
              <small>{incident["signal_count"]} signals / {escape(incident["status"])}</small>
            </button>
            """
        )
    return "".join(rows)


def render_detail(detail: dict[str, Any] | None, *, banner: str | None = None, banner_kind: str = "info") -> str:
    if detail is None:
        return """
        <div class="empty-detail">
          <div>
            <h3>Select an incident</h3>
            <p>The detail pane will show status, linked raw signals, and RCA fields.</p>
          </div>
        </div>
        """

    rca = detail.get("rca") or {}
    signal_markup = "".join(
        f"""
        <article class="signal-card">
          <header class="signal-head">
            <strong>{escape(signal["component_id"])}</strong>
            <time>{format_ts(signal["observed_at"])}</time>
          </header>
          <p class="signal-message">{escape(signal["message"])}</p>
          <small class="signal-meta">{escape(signal["signal_kind"])} / metadata keys: {', '.join(sorted(signal["metadata"].keys())) or 'none'}</small>
        </article>
        """
        for signal in detail.get("raw_signals", [])[-12:]
    ) or '<p class="muted">No raw signals recorded yet.</p>'

    banner_markup = ""
    if banner:
        banner_markup = f'<div class="banner banner-{banner_kind}">{escape(banner)}</div>'

    return f"""
    <section class="detail-shell" hx-get="/ui/incidents/{detail["id"]}" hx-trigger="every 5s" hx-target="this" hx-swap="innerHTML">
      {banner_markup}
      <header class="detail-summary">
        <div>
          <p class="kicker">{escape(detail["severity"])} / {escape(detail["component_type"])}</p>
          <h2 class="incident-title">{escape(detail["component_id"])}</h2>
          <p>{escape(detail["title"])}</p>
        </div>
        <dl class="summary-grid">
          <div class="summary-item"><dt>Status</dt><dd>{escape(detail["status"])}</dd></div>
          <div class="summary-item"><dt>Signals</dt><dd>{detail["signal_count"]}</dd></div>
          <div class="summary-item"><dt>MTTR</dt><dd>{format_duration(detail.get("mttr_seconds"))}</dd></div>
          <div class="summary-item"><dt>Alert route</dt><dd>{escape(detail["alert_channel"])}</dd></div>
        </dl>
      </header>

      <section class="status-actions">
        <form hx-post="/ui/incidents/{detail["id"]}/status" hx-target="#detail-panel" hx-swap="innerHTML">
          <input type="hidden" name="status" value="INVESTIGATING">
          <button class="action-button secondary" type="submit">Mark Investigating</button>
        </form>
        <form hx-post="/ui/incidents/{detail["id"]}/status" hx-target="#detail-panel" hx-swap="innerHTML">
          <input type="hidden" name="status" value="RESOLVED">
          <button class="action-button secondary" type="submit">Mark Resolved</button>
        </form>
        <form hx-post="/ui/incidents/{detail["id"]}/status" hx-target="#detail-panel" hx-swap="innerHTML">
          <input type="hidden" name="status" value="CLOSED">
          <button class="action-button" type="submit">Close Incident</button>
        </form>
      </section>

      <section class="detail-grid">
        <div class="detail-section">
          <div class="section-header">
            <h3 class="section-title">Linked raw signals</h3>
            <span>Latest 12 entries</span>
          </div>
          <div class="signal-stream">
            {signal_markup}
          </div>
        </div>

        <div class="detail-section">
          <div class="section-header">
            <h3 class="section-title">Root cause analysis</h3>
            <span>Required before closing</span>
          </div>
          <form class="rca-form" hx-post="/ui/incidents/{detail["id"]}/rca" hx-target="#detail-panel" hx-swap="innerHTML">
            <div class="form-grid">
              <label>
                <span>Incident start</span>
                <input type="datetime-local" name="start_time" value="{format_dt_input(rca.get("start_time") or detail["first_signal_at"])}" required>
              </label>
              <label>
                <span>Incident end</span>
                <input type="datetime-local" name="end_time" value="{format_dt_input(rca.get("end_time") or detail["last_signal_at"])}" required>
              </label>
            </div>
            <label>
              <span>Root cause category</span>
              <select name="root_cause_category" required>
                {render_category_options(rca.get("root_cause_category"))}
              </select>
            </label>
            <label>
              <span>Fix applied</span>
              <textarea name="fix_applied" rows="4" required>{escape(rca.get("fix_applied", ""))}</textarea>
            </label>
            <label>
              <span>Prevention steps</span>
              <textarea name="prevention_steps" rows="4" required>{escape(rca.get("prevention_steps", ""))}</textarea>
            </label>
            <button class="primary-button" type="submit">Save RCA</button>
          </form>
        </div>
      </section>
    </section>
    """


def render_category_options(selected: str | None) -> str:
    categories = [
        "Capacity",
        "Dependency Failure",
        "Deployment Regression",
        "Configuration Drift",
        "Network Partition",
        "Data Corruption",
    ]
    options = ['<option value="">Select a category</option>']
    for category in categories:
        is_selected = ' selected="selected"' if selected == category else ""
        options.append(f'<option value="{escape(category)}"{is_selected}>{escape(category)}</option>')
    return "".join(options)
