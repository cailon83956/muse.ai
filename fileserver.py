"""File server don gian: serve thu muc data/jobs/ qua HTTP de chia se file lon.
Chay: python fileserver.py  (hoac qua systemd). Mac dinh port 8000.
Link file: http://<host>:<port>/<job-id>/<ten-file> (vd: .../becf9f0a/dubbed.mp4)
"""
import http.server
import os
import socketserver
from pathlib import Path

from dub.config import SETTINGS

PORT = int(os.getenv("FILE_SERVER_PORT", "8000"))
# Serve thu muc jobs de link dang <base>/<job-id>/<file>
DIRECTORY = SETTINGS.jobs_dir


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def log_message(self, fmt, *args):
        # Giam noise
        pass


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    os.chdir(str(DIRECTORY))
    with ThreadedServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"File server serving {DIRECTORY} on port {PORT}", flush=True)
        httpd.serve_forever()