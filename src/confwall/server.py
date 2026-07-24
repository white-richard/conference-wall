"""HTTP server implementation using ThreadingHTTPServer for confwall."""

import logging
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfwallRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler serving files with explicit cache headers."""

    def end_headers(self) -> None:
        path_lower = self.path.lower().split("?")[0]
        if path_lower.endswith((".html", ".json")) or path_lower == "/":
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        elif "/images/" in path_lower or path_lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")

        super().end_headers()


def run_server(directory: str | Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the ThreadingHTTPServer serving static files from directory."""
    dir_path = Path(directory).resolve()
    if not dir_path.exists():
        raise FileNotFoundError(f"Build directory does not exist: {dir_path}")

    class CustomHandler(ConfwallRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dir_path), **kwargs)

    try:
        server = ThreadingHTTPServer((host, port), CustomHandler)
    except OSError as e:
        logger.error(f"Failed to bind server to {host}:{port}: {e}")
        sys.exit(1)

    logger.info(f"Serving confwall slideshow from {dir_path} at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down.")
    finally:
        server.server_close()
