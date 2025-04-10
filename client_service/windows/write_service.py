#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
from msr605x import MSR605X, set_bpc_bpi, set_coercivity, write_card, finalize_device
from waitress import serve

app = Flask(__name__)
CORS(app)

@app.route("/write", methods=["POST"])
def write():
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
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=5001)
