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
    <div class="kpi-rail">
      <section>
        <span>Queue depth</span>
        <strong>{health["queue_depth"]}</strong>
      </section>
      <section>
        <span>Signals / sec</span>
        <strong>{health["throughput_per_second"]:.2f}</strong>
      </section>
      <section>
        <span>Active incidents</span>
        <strong>{len(incidents)}</strong>
      </section>
      <section>
        <span>P0s in play</span>
        <strong>{p0_count}</strong>
      </section>
    </div>
    """


def render_incident_feed(incidents: list[dict[str, Any]]) -> str:
    if not incidents:
        return """
        <div class="empty-state">
          <p>No active incidents.</p>
          <span>Post signals to <code>/api/signals</code> or run the sample scenario to populate the dashboard.</span>
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
              <span class="eyebrow">{incident["severity"]} • {escape(incident["component_type"])}</span>
              <strong>{escape(incident["component_id"])}</strong>
              <p>{escape(incident["title"])}</p>
              <small>{incident["signal_count"]} signals • {escape(incident["status"])}</small>
            </button>
            """
        )
    return "".join(rows)


def render_detail(detail: dict[str, Any] | None, *, banner: str | None = None, banner_kind: str = "info") -> str:
    if detail is None:
        return """
        <div class="empty-detail">
          <p>Select an incident from the live feed.</p>
          <span>The detail pane will show linked raw signals, lifecycle controls, and the RCA form.</span>
        </div>
        """

    severity_class = SEVERITY_CLASSES[detail["severity"]]
    rca = detail.get("rca") or {}
    signal_markup = "".join(
        f"""
        <article class="signal-line">
          <header>
            <strong>{escape(signal["component_id"])}</strong>
            <time>{format_ts(signal["observed_at"])}</time>
          </header>
          <p>{escape(signal["message"])}</p>
          <small>{escape(signal["signal_kind"])} • metadata keys: {', '.join(sorted(signal["metadata"].keys())) or 'none'}</small>
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
      <header class="detail-hero {severity_class}">
        <div>
          <span class="eyebrow">{escape(detail["severity"])} • {escape(detail["component_type"])}</span>
          <h2>{escape(detail["component_id"])}</h2>
          <p>{escape(detail["title"])}</p>
        </div>
        <dl>
          <div><dt>Status</dt><dd>{escape(detail["status"])}</dd></div>
          <div><dt>Signals</dt><dd>{detail["signal_count"]}</dd></div>
          <div><dt>MTTR</dt><dd>{format_duration(detail.get("mttr_seconds"))}</dd></div>
          <div><dt>Alert route</dt><dd>{escape(detail["alert_channel"])}</dd></div>
        </dl>
      </header>

      <section class="status-actions">
        <form hx-post="/ui/incidents/{detail["id"]}/status" hx-target="#detail-panel" hx-swap="innerHTML">
          <input type="hidden" name="status" value="INVESTIGATING">
          <button type="submit">Mark Investigating</button>
        </form>
        <form hx-post="/ui/incidents/{detail["id"]}/status" hx-target="#detail-panel" hx-swap="innerHTML">
          <input type="hidden" name="status" value="RESOLVED">
          <button type="submit">Mark Resolved</button>
        </form>
        <form hx-post="/ui/incidents/{detail["id"]}/status" hx-target="#detail-panel" hx-swap="innerHTML">
          <input type="hidden" name="status" value="CLOSED">
          <button type="submit">Close Incident</button>
        </form>
      </section>

      <section class="detail-columns">
        <div class="signal-stream">
          <div class="section-heading">
            <h3>Linked raw signals</h3>
            <span>Querying the raw JSONL audit sink</span>
          </div>
          {signal_markup}
        </div>

        <div class="rca-panel">
          <div class="section-heading">
            <h3>Root cause analysis</h3>
            <span>Required before closing the incident</span>
          </div>
          <form class="rca-form" hx-post="/ui/incidents/{detail["id"]}/rca" hx-target="#detail-panel" hx-swap="innerHTML">
            <label>
              <span>Incident start</span>
              <input type="datetime-local" name="start_time" value="{format_dt_input(rca.get("start_time") or detail["first_signal_at"])}" required>
            </label>
            <label>
              <span>Incident end</span>
              <input type="datetime-local" name="end_time" value="{format_dt_input(rca.get("end_time") or detail["last_signal_at"])}" required>
            </label>
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
            <button type="submit">Save RCA</button>
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
