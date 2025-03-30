#!/usr/bin/env python3
from flask import Flask, jsonify
from flask_cors import CORS
from msr605x import read_card_data

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route("/read", methods=["GET"])
def read():
    try:
        data = read_card_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
