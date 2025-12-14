import logging
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from msr605x import read_card_data
from waitress import serve

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Allow only your webapp origin
CORS(app,
     resources={r"/*": {"origins": "https://app.mustbetan.com"}},
     supports_credentials=False,  # set True only if you use cookies/credentials
     max_age=600)

@app.after_request
def add_pna_headers(resp):
    # Critical for public → localhost requests
    resp.headers["Access-Control-Allow-Private-Network"] = "true"
    # Good to be explicit for CORS preflight expectations:
    if request.method == "OPTIONS":
        resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        # Add any custom headers your fetch may send (e.g., Content-Type)
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

@app.route("/read", methods=["GET", "OPTIONS"])
def read():
    if request.method == "OPTIONS":
        # Minimal OK preflight response
        return make_response(("", 204))
    try:
        data = read_card_data()
        return jsonify(data)
    except Exception as e:
        app.logger.exception("Error reading card data")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, ssl_context=("127.0.0.1+1.pem", "127.0.0.1+1-key.pem"))
