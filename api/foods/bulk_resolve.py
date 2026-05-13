from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from nutrition_app.api.vercel_runtime import handle_bulk_resolve, json_response


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        response = handle_bulk_resolve(raw_body)
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        self.wfile.write(response.body)

    def do_GET(self) -> None:
        response = json_response({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        self.wfile.write(response.body)

    def log_message(self, format: str, *args) -> None:
        return
