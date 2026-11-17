"""Bounded asynchronous IPC to an owned small CPU VAD worker."""

import asyncio
import json
import os
import subprocess
import sys
from app.core.config import ROOT
from app.core.errors import SireError
from app.voice.vad import POLICY


class VadProcess:
    """Keep optional neural imports out of the API and terminate only the owned worker."""

    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None

    async def start(self) -> dict:
        """Verify actual worker startup before acknowledging detector readiness."""
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.voice.vad_worker",
            cwd=ROOT,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=2100000,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            ),
        )
        return await self._read()

    async def _read(self) -> dict:
        assert self.process is not None and self.process.stdout is not None
        try:
            line = await asyncio.wait_for(
                self.process.stdout.readline(), POLICY["worker_timeout_seconds"]
            )
            result = json.loads(line)
            if result.get("error"):
                raise SireError(
                    result["error"]["code"], result["error"]["message"], 422
                )
            return result
        except (TimeoutError, ValueError) as exc:
            raise SireError(
                "vad_worker_failed",
                "The local VAD worker failed or timed out; use manual recording.",
                503,
            ) from exc

    async def call(self, request: dict) -> dict:
        """Send one explicit frame/control; no file paths or executable operations cross this boundary."""
        if (
            self.process is None
            or self.process.returncode is not None
            or self.process.stdin is None
        ):
            raise SireError(
                "vad_worker_closed",
                "The local voice detector is no longer available.",
                503,
            )
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        await self.process.stdin.drain()
        return await self._read()

    async def close(self) -> None:
        """Release the actual child process on stop, disconnect or application shutdown."""
        if self.process is not None:
            if self.process.returncode is None:
                self.process.kill()
            await self.process.wait()
            self.process = None
