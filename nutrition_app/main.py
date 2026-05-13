import argparse

from nutrition_app.api.server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the nutrition tracking web app.")
    parser.add_argument("--host", default=None, help="Bind host. Defaults to app settings.")
    parser.add_argument("--port", type=int, default=None, help="Bind port. Defaults to app settings.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_server(host=args.host, port=args.port)
    return 0

