"""Loopback-only disposable server for genuine stream disconnect/cancellation probes."""

from app.api.main import create_app
from pathlib import Path
from fastapi import FastAPI


def create_probe_app(state_dir: Path | None = None) -> FastAPI:
    """Place the disposable status route before the production SPA catch-all."""
    application = create_app(state_dir=state_dir, probe_model=False)

    @application.get("/__stress_status")
    def status() -> dict:
        """Read actual job counts on the disposable server, never production."""
        return {
            "active_jobs": len(application.state.chat.jobs),
            "active_conversations": len(application.state.chat.active_conversations),
        }

    route = application.router.routes[-1]
    if getattr(route, "endpoint", None) is not status:
        raise RuntimeError("Unexpected probe-route order")
    application.router.routes.remove(route)
    application.router.routes.insert(0, route)
    return application


app = create_probe_app()
