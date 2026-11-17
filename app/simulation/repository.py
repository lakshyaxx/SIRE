"""Read-only observable access with graph scope and a strict two-clock historical fence."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.core.errors import SireError

OBSERVABLE_TABLES = {"scenarios", "assets", "edges", "telemetry", "events"}


def utc(value: str) -> str:
    """Require timezone-aware UTC-normalized timestamps; never guess a local zone."""
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Timezone required")
        return stamp.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError) as exc:
        raise SireError(
            "invalid_timestamp", "Use an ISO timestamp with a timezone."
        ) from exc


class Observations:
    """Only this whitelisted read-only database reaches investigator tools/API."""

    def __init__(self, directory: Path) -> None:
        self.path = (directory / "observations.sqlite3").resolve()

    def query(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        """Execute internal reads; SQLite denies truth reads, writes, ATTACH and arbitrary databases."""
        if not self.path.is_file():
            raise SireError(
                "scenarios_unavailable",
                "Generate local scenarios with scripts/seed_scenarios.py.",
                503,
            )

        def authorize(
            action: int,
            table: str | None,
            column: str | None,
            database: str | None,
            trigger: str | None,
        ) -> int:
            if action in {
                sqlite3.SQLITE_SELECT,
                sqlite3.SQLITE_FUNCTION,
                sqlite3.SQLITE_RECURSIVE,
            }:
                return sqlite3.SQLITE_OK
            if (
                action == sqlite3.SQLITE_READ
                and table in OBSERVABLE_TABLES
                and database == "main"
            ):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        with sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            db.set_authorizer(authorize)
            return [dict(row) for row in db.execute(sql, args)]

    def scenarios(self) -> list[dict]:
        """List anonymous trial metadata, never hidden mechanism labels."""
        return [
            json.loads(row["payload"])
            for row in self.query("SELECT payload FROM scenarios ORDER BY id")
        ]

    def scenario(self, identifier: str) -> dict:
        """Resolve an explicitly selected scenario scope."""
        rows = self.query("SELECT payload FROM scenarios WHERE id=?", (identifier,))
        if not rows:
            raise SireError("scenario_missing", "Scenario not found.", 404)
        return json.loads(rows[0]["payload"])

    def cutoff(self, scenario_id: str, as_of: str | None = None) -> str:
        """Validate requested replay time against the actual public availability range."""
        scenario = self.scenario(scenario_id)
        cutoff = utc(as_of or scenario["reference_at"])
        if not scenario["starts_at"] <= cutoff <= scenario["ends_at"]:
            raise SireError(
                "time_outside_scenario",
                "Requested time is outside this scenario's availability range.",
            )
        return cutoff

    def assets(self, scenario_id: str) -> list[dict]:
        """Return only assets from a known selected scenario."""
        self.scenario(scenario_id)
        return [
            json.loads(r["payload"])
            for r in self.query(
                "SELECT payload FROM assets WHERE scenario_id=? ORDER BY id",
                (scenario_id,),
            )
        ]

    def asset(self, scenario_id: str, asset_id: str) -> dict:
        """Reject nonexistent or cross-scenario asset identities."""
        rows = self.query(
            "SELECT payload FROM assets WHERE scenario_id=? AND id=?",
            (scenario_id, asset_id),
        )
        if not rows:
            raise SireError(
                "asset_missing", "Asset is absent from the selected scenario.", 404
            )
        return json.loads(rows[0]["payload"])

    def relations(
        self,
        scenario_id: str,
        asset_id: str,
        as_of: str | None = None,
        depth: int = 1,
        direction: str = "both",
    ) -> list[dict]:
        """Traverse explicit typed edges only, preserving direction and validity provenance."""
        self.asset(scenario_id, asset_id)
        cutoff = self.cutoff(scenario_id, as_of)
        if depth not in {1, 2} or direction not in {"both", "incoming", "outgoing"}:
            raise SireError(
                "invalid_graph_scope",
                "Graph depth must be 1 or 2 and direction incoming/outgoing/both.",
            )
        edges = [
            json.loads(r["payload"])
            for r in self.query(
                "SELECT payload FROM edges WHERE scenario_id=?", (scenario_id,)
            )
        ]
        edges = [
            e
            for e in edges
            if e["valid_from"] <= cutoff
            and (e["valid_to"] is None or cutoff < e["valid_to"])
        ]
        visited, frontier, result = {asset_id}, {asset_id}, []
        for level in range(depth):
            following = set()
            for e in edges:
                if (direction in {"both", "outgoing"} and e["source"] in frontier) or (
                    direction in {"both", "incoming"} and e["target"] in frontier
                ):
                    if e not in result:
                        result.append(e)
                    following.update({e["source"], e["target"]} - visited)
            visited.update(following)
            frontier = following
        return result

    def telemetry(
        self,
        scenario_id: str,
        asset_id: str,
        as_of: str | None = None,
        start: str | None = None,
        limit: int = 5000,
        offset: int = 0,
    ) -> list[dict]:
        """Apply observed_at AND available_at fences before any analytics or pagination."""
        self.asset(scenario_id, asset_id)
        cutoff = self.cutoff(scenario_id, as_of)
        beginning = utc(start) if start else self.scenario(scenario_id)["starts_at"]
        if beginning > cutoff or limit < 1 or limit > 5000 or offset < 0:
            raise SireError("invalid_window", "Invalid time window or pagination.")
        return self.query(
            "SELECT * FROM telemetry WHERE scenario_id=? AND asset_id=? AND observed_at>=? AND observed_at<=? AND available_at<=? ORDER BY observed_at,channel LIMIT ? OFFSET ?",
            (scenario_id, asset_id, beginning, cutoff, cutoff, limit, offset),
        )

    def events(
        self,
        scenario_id: str,
        as_of: str | None = None,
        asset_ids: list[str] | None = None,
    ) -> list[dict]:
        """Exclude late-entered notes until their actual information-availability time."""
        cutoff = self.cutoff(scenario_id, as_of)
        rows = self.query(
            "SELECT * FROM events WHERE scenario_id=? AND observed_at<=? AND available_at<=? ORDER BY observed_at,id",
            (scenario_id, cutoff, cutoff),
        )
        return [r for r in rows if not asset_ids or r["asset_id"] in asset_ids]
