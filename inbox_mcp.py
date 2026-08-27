import json
import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import sublime

HOST = "127.0.0.1"
PORT_START = 8766
PORT_TRIES = 20

_server = None
_thread = None
_url = None

TOOLS = [
    {
        "name": "new_note",
        "description": "Create a new Inbox note in Sublime Text and save it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "First-line title"},
                "content": {"type": "string", "description": "Note body"},
            },
            "required": [],
        },
    },
    {
        "name": "list_notes",
        "description": "List recent notes in the Inbox folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max notes (default 30)"},
            },
        },
    },
    {
        "name": "read_note",
        "description": "Read one Inbox note. Path must be inside the inbox folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or inbox-relative path"},
            },
            "required": ["path"],
        },
    },
]


def _run_on_ui(fn, timeout=8):
    box = {}
    done = threading.Event()

    def go():
        try:
            box["ok"] = fn()
        except Exception as exc:
            box["err"] = str(exc)
        done.set()

    sublime.set_timeout(go, 0)
    if not done.wait(timeout):
        raise RuntimeError("Sublime timed out")
    if "err" in box:
        raise RuntimeError(box["err"])
    return box.get("ok")


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _text(text):
    return {"content": [{"type": "text", "text": text}]}


def _safe_inbox_path(raw):
    from .inbox import inbox_path

    folder = os.path.abspath(inbox_path())
    path = raw if os.path.isabs(raw) else os.path.join(folder, raw)
    path = os.path.abspath(path)
    try:
        if os.path.commonpath([path, folder]) != folder:
            return None
    except ValueError:
        return None
    return path


def _call_tool(name, args):
    from . import inbox

    args = args or {}
    if name == "new_note":
        content = args.get("content") or ""
        title = args.get("title") or ""
        if not str(content).strip() and not str(title).strip():
            return _text("empty note")
        path = _run_on_ui(lambda: inbox.create_inbox_note(content, title))
        return _text(path or "could not create note")
    if name == "list_notes":
        folder = inbox.inbox_path()
        os.makedirs(folder, exist_ok=True)
        limit = int(args.get("limit") or 30)
        names = []
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and not name.startswith("."):
                names.append((os.path.getmtime(full), full))
        names.sort(reverse=True)
        lines = [p for _, p in names[: max(1, min(limit, 100))]]
        return _text("\n".join(lines) if lines else "(empty inbox)")
    if name == "read_note":
        path = _safe_inbox_path(args.get("path") or "")
        if not path or not os.path.isfile(path):
            return _text("note not found")
        with open(path, "r", encoding="utf-8") as fh:
            return _text(fh.read())
    raise ValueError("unknown tool: " + name)


def handle_rpc(msg):
    if not isinstance(msg, dict):
        return _err(None, -32600, "invalid request")
    method = msg.get("method")
    req_id = msg.get("id")
    if method is None:
        return None
    if req_id is None and str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "inbox", "version": "1.0.0"},
        })
    if method == "ping":
        return _ok(req_id, {})
    if method == "tools/list":
        return _ok(req_id, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            return _ok(req_id, _call_tool(params.get("name"), params.get("arguments")))
        except Exception as exc:
            return _ok(req_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            })
    if method in ("resources/list", "prompts/list"):
        key = "resources" if method.startswith("resources") else "prompts"
        return _ok(req_id, {key: []})
    return _err(req_id, -32601, "method not found: " + str(method))


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, MCP-Protocol-Version, Mcp-Session-Id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/") not in ("/mcp", "/sse"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(b": ok\n\n")
        except Exception:
            pass

    def do_POST(self):
        if self.path.rstrip("/") not in ("/mcp", "/message"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self.send_error(400)
            return
        if isinstance(payload, list):
            replies = [r for r in (handle_rpc(item) for item in payload) if r]
        else:
            reply = handle_rpc(payload)
            replies = reply
        if replies is None:
            self.send_response(202)
            self._cors()
            self.end_headers()
            return
        body = json.dumps(replies).encode("utf-8")
        accept = self.headers.get("Accept") or ""
        self.send_response(200)
        self._cors()
        if "text/event-stream" in accept and "application/json" not in accept:
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b"event: message\ndata: " + body + b"\n\n")
            return
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _write_discovery(url):
    path = os.path.join(sublime.packages_path(), "User", "Inbox.mcp.json")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"url": url, "type": "http"}, fh, indent=2)
            fh.write("\n")
    except OSError:
        pass


def start():
    global _server, _thread, _url
    stop()
    last_err = None
    for port in range(PORT_START, PORT_START + PORT_TRIES):
        try:
            server = _Server((HOST, port), _Handler)
            _server = server
            _url = "http://{}:{}/mcp".format(HOST, port)
            _thread = threading.Thread(target=server.serve_forever, name="InboxMCP")
            _thread.daemon = True
            _thread.start()
            _write_discovery(_url)
            print("Inbox MCP: " + _url)
            return
        except OSError as exc:
            last_err = exc
    print("Inbox MCP: failed to bind ({})".format(last_err))


def stop():
    global _server, _thread, _url
    server = _server
    _server = None
    _url = None
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
    _thread = None


def url():
    return _url
