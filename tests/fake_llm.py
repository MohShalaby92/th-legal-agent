"""Fake OpenAI-compatible LLM for an end-to-end privacy test. Logs every request it receives."""
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = sys.argv[1]
OUT = sys.argv[2]
TOKEN = re.compile(r"⟦NID-\d+[^⟧]*⟧")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send({"object": "list", "data": [{"id": "fake-model", "object": "model", "context_length": 200000}]})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(raw + "\n")
        body = json.loads(raw)
        msgs = body.get("messages", [])
        has_tool = any(m.get("role") == "tool" for m in msgs)
        users = [m for m in msgs if m.get("role") == "user"]
        user_raw = json.dumps(users[-1], ensure_ascii=False) if users else raw
        if not has_tool:
            m = TOKEN.search(user_raw)
            tok = m.group(0) if m else "NO_TOKEN_FOUND"
            cmd = f"echo {tok} > {OUT}"
            msg = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "terminal", "arguments": json.dumps({"command": cmd}, ensure_ascii=False)}}]}
            finish = "tool_calls"
        else:
            msg = {"role": "assistant", "content": "تم. الرقم المطلوب هو " + (TOKEN.search(raw).group(0) if TOKEN.search(raw) else "?")}
            finish = "stop"
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            delta = dict(msg)
            if delta.get("tool_calls"):
                delta["tool_calls"] = [dict(delta["tool_calls"][0], index=0)]
            chunks = [{"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                      {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}]
            for c in chunks:
                c.update({"id": "x", "object": "chat.completion.chunk", "created": int(time.time()), "model": "fake-model"})
                self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            return
        self._send({"id": "x", "object": "chat.completion", "created": int(time.time()), "model": "fake-model",
                    "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})


HTTPServer(("127.0.0.1", 8765), H).serve_forever()
