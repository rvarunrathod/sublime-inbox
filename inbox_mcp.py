import json
import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import sublime

HOST = "127.0.0.1"
PORT_START = 8766
PORT_TRIES = 20

_server = None
_thread = None
_url = None

def _inbox_folder():
    from .inbox import inbox_path
    return os.path.abspath(inbox_path())


def _instructions():
    folder = _inbox_folder()
    return (
        "Inbox notes are markdown files in {0}. "
        "Use new_note to create one; Sublime names it "
        "YYYY-MM-DD-HHMMSS-first-line.md and parks it. "
        "List, read, search, and edit files in {0} with your normal file tools."
    ).format(folder)


def _tools():
    folder = _inbox_folder()
    return [
        {
            "name": "new_note",
            "description": (
                "Create a new Inbox note and save it in {0}. "
                "Existing notes are ordinary markdown files in that folder — "
                "list, read, search, or edit them with your file tools."
            ).format(folder),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "First-line title"},
                    "content": {"type": "string", "description": "Note body"},
                },
                "required": [],
            },
        },
    ]


def _resources():
    folder = _inbox_folder()
    return [
        {
            "uri": Path(folder).as_uri(),
            "name": "inbox",
            "description": (
                "Folder of Inbox notes (markdown) at {}. "
                "Use file tools to list, read, search, and edit."
            ).format(folder),
            "mimeType": "text/plain",
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
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
            },
            "serverInfo": {"name": "inbox", "version": "1.0.0"},
            "instructions": _instructions(),
        })
    if method == "ping":
        return _ok(req_id, {})
    if method == "tools/list":
        return _ok(req_id, {"tools": _tools()})
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            return _ok(req_id, _call_tool(params.get("name"), params.get("arguments")))
        except Exception as exc:
            return _ok(req_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            })
    if method == "resources/list":
        return _ok(req_id, {"resources": _resources()})
    if method == "resources/read":
        params = msg.get("params") or {}
        uri = params.get("uri") or ""
        folder = _inbox_folder()
        if uri.rstrip("/") != Path(folder).as_uri().rstrip("/"):
            return _err(req_id, -32002, "unknown resource")
        return _ok(req_id, {
            "contents": [{
                "uri": Path(folder).as_uri(),
                "mimeType": "text/plain",
                "text": _instructions(),
            }],
        })
    if method == "prompts/list":
        return _ok(req_id, {"prompts": []})
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


def _discovery_path():
    return os.path.join(sublime.packages_path(), "User", "Inbox.mcp.json")


def _write_discovery(url):
    try:
        with open(_discovery_path(), "w", encoding="utf-8") as fh:
            json.dump({"url": url, "type": "http"}, fh, indent=2)
            fh.write("\n")
    except OSError:
        pass


def _clear_discovery():
    try:
        os.remove(_discovery_path())
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
        print("Inbox MCP: off")
    _thread = None
    _clear_discovery()


def running():
    return _server is not None


def url():
    return _url
