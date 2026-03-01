"""Apple Calendar integration via JXA (JavaScript for Automation) / osascript."""

import subprocess
from typing import Any

from max_ai.tools.base import BaseTool, ToolDefinition


def _esc(s: str) -> str:
    """Escape a string for safe embedding in a JXA double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _run_jxa(script: str) -> str:
    """Run a JXA script via osascript and return stdout, raising on error."""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "osascript error")
    return result.stdout.strip()


class CalendarTools(BaseTool):
    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="calendar_list_calendars",
                description="List all Apple Calendar names available on this Mac.",
                input_schema={"type": "object", "properties": {}},
            ),
            ToolDefinition(
                name="calendar_list_events",
                description=(
                    "List events within a date range. Returns uid, title, start, end, "
                    "calendar name, and location for each event."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": (
                                "Start of range as ISO 8601 datetime, e.g. '2026-02-28T00:00:00'"
                            ),
                        },
                        "end_date": {
                            "type": "string",
                            "description": (
                                "End of range as ISO 8601 datetime, e.g. '2026-03-07T23:59:59'"
                            ),
                        },
                        "calendar_name": {
                            "type": "string",
                            "description": "Optional: filter to a specific calendar name.",
                        },
                    },
                    "required": ["start_date", "end_date"],
                },
            ),
            ToolDefinition(
                name="calendar_create_event",
                description="Create a new event in Apple Calendar.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Event title / summary"},
                        "start": {
                            "type": "string",
                            "description": "Start datetime as ISO 8601, e.g. '2026-03-05T14:00:00'",
                        },
                        "end": {
                            "type": "string",
                            "description": "End datetime as ISO 8601, e.g. '2026-03-05T15:00:00'",
                        },
                        "calendar_name": {
                            "type": "string",
                            "description": (
                                "Name of the calendar to add the event to."
                                " Defaults to the first calendar."
                            ),
                        },
                        "notes": {"type": "string", "description": "Optional notes / description"},
                        "location": {"type": "string", "description": "Optional location"},
                    },
                    "required": ["title", "start", "end"],
                },
            ),
            ToolDefinition(
                name="calendar_update_event",
                description="Update fields of an existing event identified by its uid.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "uid": {
                            "type": "string",
                            "description": "Event UID (from calendar_list_events)",
                        },
                        "title": {"type": "string", "description": "New title"},
                        "start": {"type": "string", "description": "New start as ISO 8601"},
                        "end": {"type": "string", "description": "New end as ISO 8601"},
                        "notes": {"type": "string", "description": "New notes"},
                        "location": {"type": "string", "description": "New location"},
                    },
                    "required": ["uid"],
                },
            ),
            ToolDefinition(
                name="calendar_delete_event",
                description=(
                    "Delete an event by uid. When confirmed=false (default), returns event details "
                    "and asks Claude to confirm with the user before proceeding. "
                    "Set confirmed=true only after the user has explicitly said yes."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "uid": {"type": "string", "description": "Event UID to delete"},
                        "confirmed": {
                            "type": "boolean",
                            "description": "Must be true to actually delete. Default false.",
                        },
                    },
                    "required": ["uid"],
                },
            ),
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        try:
            return _dispatch(tool_name, tool_input)
        except Exception as e:
            return f"Calendar error: {e}"


def _dispatch(name: str, inp: dict[str, Any]) -> str:
    if name == "calendar_list_calendars":
        return _list_calendars()
    elif name == "calendar_list_events":
        return _list_events(inp["start_date"], inp["end_date"], inp.get("calendar_name"))
    elif name == "calendar_create_event":
        return _create_event(
            title=inp["title"],
            start=inp["start"],
            end=inp["end"],
            calendar_name=inp.get("calendar_name"),
            notes=inp.get("notes"),
            location=inp.get("location"),
        )
    elif name == "calendar_update_event":
        return _update_event(
            uid=inp["uid"],
            title=inp.get("title"),
            start=inp.get("start"),
            end=inp.get("end"),
            notes=inp.get("notes"),
            location=inp.get("location"),
        )
    elif name == "calendar_delete_event":
        return _delete_event(uid=inp["uid"], confirmed=inp.get("confirmed", False))
    return f"Unknown calendar tool: {name}"


def _list_calendars() -> str:
    script = """
const app = Application("Calendar");
app.calendars().map(c => c.name()).join("\\n");
"""
    result = _run_jxa(script)
    if not result:
        return "No calendars found."
    return result


def _list_events(start_date: str, end_date: str, calendar_name: str | None) -> str:
    cal_filter = f'if (cal.name() !== "{_esc(calendar_name)}") continue;' if calendar_name else ""
    script = f"""
const app = Application("Calendar");
const start = new Date("{_esc(start_date)}");
const end = new Date("{_esc(end_date)}");
const rows = [];
for (const cal of app.calendars()) {{
  {cal_filter}
  for (const ev of cal.events()) {{
    const evStart = ev.startDate();
    if (evStart >= start && evStart <= end) {{
      const uid = ev.uid();
      const summary = ev.summary() || "";
      const evEnd = ev.endDate();
      const loc = ev.location() || "";
      const row = [uid, summary, evStart.toISOString(),
        evEnd.toISOString(), cal.name(), loc];
      rows.push(row.join("\\t"));
    }}
  }}
}}
rows.join("\\n");
"""
    result = _run_jxa(script)
    if not result:
        return "No events found in the given range."
    lines = []
    for row in result.splitlines():
        parts = row.split("\t")
        if len(parts) >= 5:
            uid, title, start, end, cal, *rest = parts
            loc = rest[0] if rest else ""
            line = f"[{cal}] {title} | {start} → {end} | uid: {uid}"
            if loc:
                line += f" | location: {loc}"
            lines.append(line)
    return "\n".join(lines) if lines else "No events found."


def _create_event(
    title: str,
    start: str,
    end: str,
    calendar_name: str | None,
    notes: str | None,
    location: str | None,
) -> str:
    cal_lookup = (
        f'app.calendars.byName("{_esc(calendar_name)}")' if calendar_name else "app.calendars()[0]"
    )
    notes_line = f'ev.description = "{_esc(notes)}";' if notes else ""
    location_line = f'ev.location = "{_esc(location)}";' if location else ""
    script = f"""
const app = Application("Calendar");
const cal = {cal_lookup};
const ev = app.Event({{
  summary: "{_esc(title)}",
  startDate: new Date("{_esc(start)}"),
  endDate: new Date("{_esc(end)}")
}});
cal.events.push(ev);
{notes_line}
{location_line}
ev.uid();
"""
    uid = _run_jxa(script)
    return f"Event created: '{title}' from {start} to {end}. UID: {uid}"


def _update_event(
    uid: str,
    title: str | None,
    start: str | None,
    end: str | None,
    notes: str | None,
    location: str | None,
) -> str:
    updates = []
    if title is not None:
        updates.append(f'ev.summary = "{_esc(title)}";')
    if start is not None:
        updates.append(f'ev.startDate = new Date("{_esc(start)}");')
    if end is not None:
        updates.append(f'ev.endDate = new Date("{_esc(end)}");')
    if notes is not None:
        updates.append(f'ev.description = "{_esc(notes)}";')
    if location is not None:
        updates.append(f'ev.location = "{_esc(location)}";')

    if not updates:
        return "Nothing to update."

    updates_js = "\n      ".join(updates)
    script = f"""
const app = Application("Calendar");
let found = false;
for (const cal of app.calendars()) {{
  const matches = cal.events.whose({{ uid: "{_esc(uid)}" }})();
  if (matches.length > 0) {{
    const ev = matches[0];
    {updates_js}
    found = true;
    break;
  }}
}}
found ? "updated" : "not found";
"""
    result = _run_jxa(script)
    if result == "not found":
        return f"No event found with uid: {uid}"
    return f"Event {uid} updated."


def _delete_event(uid: str, confirmed: bool) -> str:
    # Lookup script used in both branches
    lookup_script = f"""
const app = Application("Calendar");
let info = null;
for (const cal of app.calendars()) {{
  const matches = cal.events.whose({{ uid: "{_esc(uid)}" }})();
  if (matches.length > 0) {{
    const ev = matches[0];
    const parts = [ev.summary() || "(no title)",
      ev.startDate().toISOString(), ev.endDate().toISOString(), cal.name()];
    info = parts.join("\\t");
    break;
  }}
}}
info || "not found";
"""
    event_info = _run_jxa(lookup_script)
    if event_info == "not found":
        return f"No event found with uid: {uid}"

    parts = event_info.split("\t")
    title, start, end, cal = parts[0], parts[1], parts[2], parts[3]

    if not confirmed:
        return (
            f"Event found: '{title}' on {start} → {end} (Calendar: {cal}). "
            f"Please confirm with the user before deleting. "
            f"Call calendar_delete_event again with confirmed=true to proceed."
        )

    delete_script = f"""
const app = Application("Calendar");
let deleted = false;
for (const cal of app.calendars()) {{
  const matches = cal.events.whose({{ uid: "{_esc(uid)}" }})();
  if (matches.length > 0) {{
    cal.events.remove(matches[0]);
    deleted = true;
    break;
  }}
}}
deleted ? "deleted" : "not found";
"""
    result = _run_jxa(delete_script)
    if result == "not found":
        return f"No event found with uid: {uid}"
    return f"Deleted event: '{title}' ({start} → {end})."
