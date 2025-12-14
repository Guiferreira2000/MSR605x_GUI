# agent.py
# Python 3.11+ tested style
# Requisitos: websocket-client, requests, certifi
#
# pip install websocket-client requests certifi

import os
import sys
import ssl
import time
import base64
import json
import logging
import threading
from urllib.parse import urljoin

import requests
from websocket import create_connection, WebSocketBadStatusException, WebSocketConnectionClosedException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("msr605x_agent")

AGENT_TOKEN  = "b7f3c1a9d6e2f4b8c0a7e9d3f1b2c4a6d8e0f3a1b5c7d9e2f4a6b8c0d1e3f5a2"
if not AGENT_TOKEN:
    # try rails env: SetEnv AGENT_TOKEN in apache vhost
    log.error("AGENT_TOKEN not set in environment. Set AGENT_TOKEN before starting.")
    # allow continuing for debug but will fail to subscribe
READ_URL = os.environ.get("READ_URL", "http://127.0.0.1:5000/read")
WRITE_URL = os.environ.get("WRITE_URL", "http://127.0.0.1:5001/write")
WS_HOST = os.environ.get("ACTION_CABLE_HOST", "app.mustbetan.com")
WS_URL = os.environ.get("ACTION_CABLE_URL", f"wss://{WS_HOST}/cable")

# timeout settings
LOCAL_TIMEOUT = int(os.environ.get("LOCAL_TIMEOUT", "8"))
RESP_TIMEOUT = int(os.environ.get("RESP_TIMEOUT", "20"))  # how long to wait local service

# helper: perform local request (GET/POST)
def do_local_request(method, path, headers=None, body_b64=None):
    headers = headers or {}
    try:
        if method == "GET":
            r = requests.get(READ_URL, headers=headers, timeout=LOCAL_TIMEOUT)
        else:  # POST
            data = b""
            if body_b64:
                try:
                    data = base64.b64decode(body_b64)
                except Exception:
                    data = body_b64.encode("utf-8")
            # forward content-type if present
            r = requests.post(WRITE_URL, headers=headers, data=data, timeout=LOCAL_TIMEOUT)
        return {
            "status": r.status_code,
            "headers": dict(r.headers),
            "body": base64.b64encode(r.content).decode("ascii")
        }
    except Exception as e:
        log.exception("Local call failed")
        return {"status": 500, "headers": {}, "body": base64.b64encode(str(e).encode()).decode("ascii")}

# build actioncable identifier JSON string
def make_identifier():
    # subscribe to LocalAgentChannel with agent_token (server expects this)
    ident = {"channel": "LocalAgentChannel"}
    if AGENT_TOKEN:
        ident["agent_token"] = AGENT_TOKEN
    return json.dumps(ident, separators=(",", ":"))

# Create websocket headers that mimic a browser (Host without :443, include Origin)
def make_ws_headers():
    headers = [
        f"Host: {WS_HOST}",                       # important: without :443
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Origin: https://{WS_HOST}",             # important: ActionCable/Apache expect Origin
        "Sec-WebSocket-Version: 13",
        "User-Agent: msr605x-agent/1.0 (+https://app.mustbetan.com)",
        # don't include Sec-WebSocket-Key here, websocket lib sets it
    ]
    return headers

# send actioncable subscribe
def send_subscribe(ws, identifier):
    payload = {"command": "subscribe", "identifier": identifier}
    ws.send(json.dumps(payload))
    log.info("Sent subscribe command: %s", payload)

# send perform('response', data) to channel
def send_response_action(ws, identifier, response_data):
    # ActionCable client -> server uses command "message" with "data" a JSON string
    data_obj = {"action": "response"}
    data_obj.update(response_data)  # expecting keys like id, status, headers, body
    payload = {
        "command": "message",
        "identifier": identifier,
        "data": json.dumps(data_obj, separators=(",", ":"))
    }
    try:
        ws.send(json.dumps(payload))
        log.info("Sent response action for id=%s status=%s", response_data.get("id"), response_data.get("status"))
    except Exception:
        log.exception("Failed sending response action")

def handle_message(ws, msg_text, identifier):
    """
    Incoming messages from server. ActionCable messages typically are JSON:
      - {"type":"ping",...}
      - {"identifier": "...", "message": {...}}
      - {"type":"confirm_subscription"}
      - {"type":"welcome"}
    For broadcasts to the channel we expect message => { "type": "request", ... }
    """
    try:
        msg = json.loads(msg_text)
    except Exception:
        log.debug("Non-JSON ws message: %s", msg_text)
        return

    # if it's a broadcast message, it usually appears under "message"
    if "message" in msg:
        message = msg["message"]
        # Our controller broadcasts payload like { type: "request", id:..., method:..., path:..., headers:..., body:... }
        if isinstance(message, dict) and message.get("type") == "request":
            req_id = message.get("id")
            method = message.get("method", "GET")
            path = message.get("path", "")
            headers = message.get("headers", {})
            body_b64 = message.get("body", "")  # already base64 (for write) or empty
            log.info("[local_proxy] received request id=%s method=%s path=%s", req_id, method, path)

            # perform local call and build response
            resp = do_local_request(method, path, headers=headers, body_b64=body_b64)
            response_payload = {
                "id": req_id,
                "status": resp.get("status", 500),
                "headers": resp.get("headers", {}),
                "body": resp.get("body", "")
            }
            # send perform('response', response_payload)
            send_response_action(ws, identifier, response_payload)
        else:
            log.debug("Message not a request: %s", message)
    elif msg.get("type") == "welcome":
        log.info("Cable welcome received.")
    elif msg.get("type") == "confirm_subscription":
        log.info("Subscription confirmed.")
    elif msg.get("type") == "ping":
        log.debug("ping from server")
    else:
        log.debug("Unhandled ws message: %s", msg)

def run_loop():
    identifier = make_identifier()
    headers = make_ws_headers()
    sslopt = {"cert_reqs": ssl.CERT_REQUIRED}
    try:
        import certifi
        sslopt["ca_certs"] = certifi.where()
    except Exception:
        log.warning("certifi not installed, using system CA bundle (may fail).")

    backoff = 1.0
    while True:
        try:
            log.info("Connecting to %s (Host header: %s)", WS_URL, headers[0].split(": ", 1)[1])
            ws = create_connection(WS_URL, header=headers, sslopt=sslopt, timeout=20)
            log.info("WebSocket connected. Sending subscribe.")
            send_subscribe(ws, identifier)

            # read loop
            backoff = 1.0
            while True:
                try:
                    msg = ws.recv()
                    if msg is None:
                        log.warning("ws.recv() returned None. Connection probably closed.")
                        break
                    # handle incoming message
                    handle_message(ws, msg, identifier)
                except WebSocketConnectionClosedException:
                    log.warning("Websocket closed by server.")
                    break
                except Exception:
                    log.exception("Error while waiting on ws.recv()")
                    break

        except WebSocketBadStatusException as e:
            # this is the 400/404/xxx from server on handshake
            log.error("Exception while connecting/handshaking: %s -+-+- %s -+-+- %s", getattr(e, "status_code", "N/A"), getattr(e, "headers", None), getattr(e, "body", None))
        except Exception:
            log.exception("Unexpected exception creating websocket connection")
        # exponential backoff
        log.warning("Websocket loop exited; will reconnect in %.1f s", backoff)
        time.sleep(backoff)
        backoff = min(backoff * 2, 60.0)

if __name__ == "__main__":
    log.info("Starting agent (token-only). READ=%s WRITE=%s AGENT_TOKEN(len)=%s", READ_URL, WRITE_URL, len(AGENT_TOKEN) if AGENT_TOKEN else 0)
    run_loop()