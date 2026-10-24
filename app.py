import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from controllers import category_controller
from controllers import product_controller
from controllers import enquiry_controller

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")


@app.route("/uploads/<path:filename>", methods=["GET"])
def serve_uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# Category APIs
@app.route("/api/categories", methods=["GET"])
def get_categories():
    return category_controller.get_categories()


# Product APIs
@app.route("/api/products", methods=["GET"])
def get_products():
    return product_controller.get_products()


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product_by_id(product_id):
    return product_controller.get_product_by_id(product_id)


# Enquiry API
@app.route("/api/enquiries", methods=["POST"])
def create_enquiry():
    return enquiry_controller.create_enquiry()


# Reference ID + Secret PIN Tracking APIs
@app.route("/api/enquiries/track-by-pin", methods=["POST"])
def track_enquiry_by_pin():
    return enquiry_controller.track_enquiry_by_pin()


@app.route("/api/enquiries/change-pin", methods=["POST"])
def change_enquiry_pin():
    return enquiry_controller.change_enquiry_pin()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
