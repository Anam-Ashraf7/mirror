"""Web layer — FastAPI backend + a minimal browser UI. Talks ONLY to MemoryEngine (ticket 10)."""

from mirror.web.app import create_app

__all__ = ["create_app"]
