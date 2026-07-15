from http.server import SimpleHTTPRequestHandler, HTTPServer
import os
import urllib.parse

PORT = 8080

BASE_PATH = "/maps"

REPO_ROOT = os.path.abspath(".")
SRC_INDEX = os.path.join(REPO_ROOT, "src", "index.html")
TRACKERS_INDEX = os.path.join(REPO_ROOT, "trackers", "index.html")

class FrontController(SimpleHTTPRequestHandler):
    # Serve files from the repo root regardless of where server.py lives.
    def translate_path(self, path: str) -> str:
        parsed = urllib.parse.urlparse(path)
        req_path = parsed.path

        # Normalize BASE_PATH handling
        if BASE_PATH:
            if req_path == BASE_PATH:
                req_path = BASE_PATH + "/"
            if not req_path.startswith(BASE_PATH + "/"):
                # Outside expected base -> map to a non-existent file so we 404.
                return os.path.join(REPO_ROOT, "__not_found__")
            req_path = req_path[len(BASE_PATH):]  # strip "/maps"

        # Map URL path -> filesystem path under repo root
        rel = req_path.lstrip("/")
        fs_path = os.path.join(REPO_ROOT, rel)

        # If URL is a directory, SimpleHTTPRequestHandler will try index.html automatically.
        # We keep that behavior by returning the directory path here.
        return fs_path

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        req_path = parsed.path

        # Strip BASE_PATH for routing decisions
        if BASE_PATH:
            if req_path == BASE_PATH:
                self.send_response(301)
                self.send_header("Location", BASE_PATH + "/")
                self.end_headers()
                return
            if not req_path.startswith(BASE_PATH + "/"):
                self.send_error(404, "Not found")
                return
            route_path = req_path[len(BASE_PATH):]  # starts with "/"
        else:
            route_path = req_path

        # Special case: /trackers/ should serve trackers/index.html if present
        if route_path == "/trackers/" or route_path == "/trackers":
            if os.path.isfile(TRACKERS_INDEX):
                self.path = (BASE_PATH + "/trackers/index.html") if BASE_PATH else "/trackers/index.html"
                return super().do_GET()

        # Compute the actual on-disk path for the requested URL
        fs_path = self.translate_path(self.path)

        # Front-controller rule:
        # If request is under /trackers/ and the target is a directory URL or doesn't exist,
        # serve src/index.html (app shell) WITHOUT copying anything.
        under_trackers = route_path.startswith("/trackers/")

        # Directory URL: "/trackers/bioenergy/" or "/trackers/bioenergy"
        looks_like_dir_url = route_path.endswith("/") or (under_trackers and not os.path.splitext(route_path)[1])

        if under_trackers:
            # If the request is for an existing file (e.g., /trackers/bioenergy/config.js), serve it normally.
            # Otherwise, serve the shared app shell.
            if os.path.isfile(fs_path):
                return super().do_GET()

            # If it's a directory URL or missing path under trackers, serve src/index.html
            if looks_like_dir_url or not os.path.exists(fs_path):
                self.path = (BASE_PATH + "/src/index.html") if BASE_PATH else "/src/index.html"
                return super().do_GET()

        # Also handy: make the repo root serve src/index.html
        if route_path == "/" or route_path == "/index.html":
            self.path = (BASE_PATH + "/src/index.html") if BASE_PATH else "/src/index.html"
            return super().do_GET()

        return super().do_GET()

if __name__ == "__main__":
    if not os.path.isfile(SRC_INDEX):
        raise SystemExit("Expected to find src/index.html at repo root.")

    server = HTTPServer(("localhost", PORT), FrontController)
    base = BASE_PATH if BASE_PATH else ""
    print(f"Serving repo root at http://localhost:{PORT}{base}/trackers/")
    print(f"Example tracker: http://localhost:{PORT}{base}/trackers/gbpt/")
    server.serve_forever()
