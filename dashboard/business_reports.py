import csv
import io
import json
import re
from datetime import UTC, datetime

import streamlit as st


def stamp_report(payload):
    return {**payload, "_generated_at": datetime.now(UTC).isoformat(timespec="seconds")}


def _value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return "" if value is None else value


def _tables(payload):
    scalars = {}
    sections = []
    for key, value in sorted(payload.items()):
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            sections.extend((f"{key}.{name}", rows) for name, rows in _tables(value))
        elif isinstance(value, list):
            if value:
                sections.append((key, value))
        else:
            scalars[key] = value
    return ([("metrics", [scalars])] if scalars else []) + sections


def _csv_cell(value):
    value = _value(value)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _markdown_cell(value):
    return (str(_value(value)).replace("\\", "\\\\").replace("|", "\\|")
            .replace("<", "&lt;").replace(">", "&gt;").replace("\n", " "))


def build_report(title, payload, filters, assumptions):
    """Serialize a loaded snapshot without network calls or a fresh timestamp."""
    metadata = {
        "title": title,
        "generated_at_utc": payload["_generated_at"],
        "period_start": payload["period_start"],
        "period_end": payload["period_end"],
        "applied_filters": {key: value for key, value in filters.items() if value is not None},
        "assumptions": list(assumptions),
    }
    tables = [("metadata", [metadata]), *_tables(payload)]
    fields = sorted({field for _, rows in tables for row in rows for field in row})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["section", *fields], lineterminator="\n")
    writer.writeheader()
    for section, rows in tables:
        for row in rows:
            writer.writerow({"section": section, **{key: _csv_cell(value) for key, value in row.items()}})

    lines = [
        f"# {title}", "", f"Generated at {metadata['generated_at_utc']}",
        f"Period {metadata['period_start']} to {metadata['period_end']}",
        f"Applied filters {_markdown_cell(metadata['applied_filters'])}",
        "", "## Assumptions", "", *[f"- {note}" for note in assumptions],
    ]
    for section, rows in tables[1:]:
        columns = sorted({field for row in rows for field in row})
        lines.extend(["", f"## {section.replace('_', ' ')}", "",
                      "| " + " | ".join(columns) + " |",
                      "| " + " | ".join("---" for _ in columns) + " |"])
        lines.extend(
            "| " + " | ".join(_markdown_cell(row.get(key)) for key in columns) + " |"
            for row in rows[:10]
        )
        if len(rows) > 10:
            lines.extend(["", f"Showing 10 of {len(rows)} rows. The CSV includes all loaded rows."])
    return output.getvalue(), "\n".join(lines) + "\n"


def report_downloads(title, payload, filters, assumptions):
    if "_generated_at" not in payload:
        st.info("Reload the analysis to create a timestamped report.")
        return
    csv_data, markdown = build_report(title, payload, filters, assumptions)
    name = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    filename = f"decisionos_{name}_{payload['period_end']}"
    left, right = st.columns(2)
    left.download_button("Download CSV report", csv_data, file_name=f"{filename}.csv",
                         mime="text/csv", on_click="ignore")
    right.download_button("Download Markdown summary", markdown, file_name=f"{filename}.md",
                          mime="text/markdown", on_click="ignore")
