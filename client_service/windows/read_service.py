import logging
from flask import Flask, jsonify
from flask_cors import CORS
from msr605x import read_card_data
from waitress import serve

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)

@app.route("/read", methods=["GET"])
def read():
    try:
        data = read_card_data()
        return jsonify(data)
    except Exception as e:
        app.logger.exception("Error reading card data")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=5000, log_socket_errors=True)
