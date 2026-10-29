"""Punto de entrada Gunicorn del Explorador territorial."""

from dashboard.app import app, server

__all__ = ["app", "server"]
