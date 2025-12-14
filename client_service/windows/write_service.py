#!/usr/bin/env python3
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from msr605x import MSR605X, set_bpc_bpi, set_coercivity, write_card, finalize_device
from waitress import serve

app = Flask(__name__)

CORS(app,
     resources={r"/*": {"origins": "https://app.mustbetan.com"}},
     supports_credentials=False,
     max_age=600)

@app.after_request
def add_pna_headers(resp):
    resp.headers["Access-Control-Allow-Private-Network"] = "true"
    if request.method == "OPTIONS":
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

@app.route("/write", methods=["POST", "OPTIONS"])
def write():
    if request.method == "OPTIONS":
        return make_response(("", 204))
    try:
        data = request.get_json() or {}
        track1 = data.get("track1", "")
        track2 = data.get("track2", "")
        track3 = data.get("track3", "")
        coercivity = data.get("coercivity", "hi")

        if not (track1 and track2 and track3):
            return jsonify({"error": "Missing track data; please supply track1, track2, and track3."}), 400

        msr = MSR605X()
        msr.connect()
        msr.reset()
        set_bpc_bpi(msr, mode="write")
        set_coercivity(msr, mode=coercivity)
        write_card(msr, track1.encode(), track2.encode(), track3.encode())
        finalize_device(msr)

        return jsonify({"message": "Write action completed", "track3": track3})
    except Exception as e:
        app.logger.exception("Error writing card")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, ssl_context=("127.0.0.1+1.pem", "127.0.0.1+1-key.pem"))
