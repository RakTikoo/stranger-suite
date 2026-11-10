"""Local mock payment API fixture (stdlib only).

Truth about this API (what the server actually does):
- POST /customers  {name}                      -> 201 {id}
- POST /charges    {customer_id, amount_cents} -> 201 {id}
    REQUIRES header X-Api-Version: 2.
- POST /refunds    {charge_id}                 -> 201 {id}
- GET  /__state                                -> counts, for the objective checker

Whether the DOCS tell the truth about the header and the field name is the
test: good docs say both, lying docs omit the header and call the field
`amount`.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_server(port=0):
    state = {"customers": 0, "charges": 0, "refunds": 0, "last": {},
             "_customer_ids": set(), "_charge_ids": set()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/__state":
                self._send(200, {k: v for k, v in state.items()
                                 if not k.startswith("_")})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                data = {}
            if self.path == "/customers":
                if not data.get("name"):
                    return self._send(400, {"error": "field 'name' is required"})
                state["customers"] += 1
                state["last"]["customer_id"] = f"cus_{state['customers']}"
                state["_customer_ids"].add(state["last"]["customer_id"])
                return self._send(201, {"id": state["last"]["customer_id"]})
            if self.path == "/charges":
                if self.headers.get("X-Api-Version") != "2":
                    return self._send(401, {"error": "X-Api-Version header is required and must be 2"})
                if "amount_cents" not in data:
                    return self._send(400, {"error": "field 'amount_cents' is required; 'amount' was removed in v2"})
                if not data.get("customer_id"):
                    return self._send(400, {"error": "field 'customer_id' is required"})
                if data["customer_id"] not in state["_customer_ids"]:
                    return self._send(400, {"error": "customer_id does not match any customer created by this API"})
                state["charges"] += 1
                state["last"]["charge_id"] = f"chg_{state['charges']}"
                state["_charge_ids"].add(state["last"]["charge_id"])
                return self._send(201, {"id": state["last"]["charge_id"]})
            if self.path == "/refunds":
                if not data.get("charge_id"):
                    return self._send(400, {"error": "field 'charge_id' is required"})
                if data["charge_id"] not in state["_charge_ids"]:
                    return self._send(400, {"error": "charge_id does not match any charge created by this API"})
                state["refunds"] += 1
                return self._send(201, {"id": f"ref_{state['refunds']}"})
            return self._send(404, {"error": "not found"})

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.state = state
    return srv


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = make_server(port)
    print(f"mock api on http://127.0.0.1:{srv.server_address[1]}", flush=True)
    srv.serve_forever()
