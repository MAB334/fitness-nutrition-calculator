from http.server import BaseHTTPRequestHandler

from nutrition_app.api.vercel_runtime import handle_health


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        response = handle_health()
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        self.wfile.write(response.body)

    def log_message(self, format: str, *args) -> None:
        return
