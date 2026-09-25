"""Local typed-decision HTTP server for agent runtimes.

Serves the Jev wire format on top of a Laya Agent from laya-mlx
(https://github.com/mizorewww/laya-mlx, Apache-2.0): ``POST /ask`` with
``{"state": ..., "questions": {...}}`` returns ``{"answers": {...}}`` where
``noul`` questions carry ``{"noul": P(true)}``, matching what
fast-jev-compaction's ``parseJevResponse``/``noulAnswer`` expect. Also exposes
``GET /health``. Requires the ``laya_mlx`` package; mirrors
``laya_mlx/server.py`` from that repository. Uses only the standard library
for the HTTP layer.
"""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from laya_mlx.agent import load
except ImportError as error:  # pragma: no cover - guidance for first run
    raise SystemExit(
        "laya_mlx is required: pip install laya-mlx "
        "(or see https://github.com/mizorewww/laya-mlx)"
    ) from error

MAX_BODY_BYTES = 20 * 1024 * 1024


class DecisionService:
    def __init__(self, agent):
        self.agent = agent
        self.lock = threading.Lock()

    def answer(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        questions = payload.get("questions")
        if not isinstance(questions, dict) or not questions:
            raise ValueError("request must contain a non-empty 'questions' object")
        state = payload.get("state", "")
        if not isinstance(state, (str, dict, list)):
            raise ValueError("state must be a string, object, or array")
        with self.lock:
            return self.agent.predict(state, questions)


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/ask":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY_BYTES:
                    raise ValueError("missing or oversized request body")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                self._send(200, service.answer(payload))
            except (ValueError, json.JSONDecodeError) as error:
                self._send(400, {"error": str(error)})
            except Exception as error:  # noqa: BLE001 - report any inference failure
                self._send(500, {"error": f"{type(error).__name__}: {error}"})

        def log_message(self, format, *args):  # noqa: A002 - stdlib signature
            return

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve Laya typed decisions over HTTP")
    parser.add_argument("--model", default="aac6fef/laya-multilingual-mlx")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--dtype", default="float16", choices=["float16", "float32", "bfloat16"])
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--device", default=None, choices=[None, "gpu", "metal", "cpu"])
    args = parser.parse_args(argv)

    agent = load(args.model, dtype=args.dtype, batch_size=args.batch_size, device=args.device)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(DecisionService(agent)))
    print(f"laya decision server on http://{args.host}:{args.port} ({args.model})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
