import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from controllers import category_controller
from controllers import product_controller
from controllers import enquiry_controller
from controllers import admin_controller

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


# =========================================================
# ADMIN PANEL ROUTES (/admin)
# =========================================================

# Admin Auth
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    return admin_controller.admin_login()

@app.route("/api/admin/me", methods=["GET"])
def get_admin_profile():
    return admin_controller.get_admin_profile()

@app.route("/api/admin/change-password", methods=["POST"])
def admin_change_password():
    return admin_controller.admin_change_password()

# Dashboard Stats
@app.route("/api/admin/stats", methods=["GET"])
def get_dashboard_stats():
    return admin_controller.get_dashboard_stats()

# Products CRUD
@app.route("/api/admin/products", methods=["GET"])
def admin_get_products():
    return admin_controller.admin_get_products()

@app.route("/api/admin/products", methods=["POST"])
def admin_create_product():
    return admin_controller.admin_create_product()

@app.route("/api/admin/products/<int:product_id>", methods=["PUT"])
def admin_update_product(product_id):
    return admin_controller.admin_update_product(product_id)

@app.route("/api/admin/products/<int:product_id>/toggle-status", methods=["PATCH"])
def admin_toggle_product_status(product_id):
    return admin_controller.admin_toggle_product_status(product_id)

@app.route("/api/admin/products/<int:product_id>", methods=["DELETE"])
def admin_delete_product(product_id):
    return admin_controller.admin_delete_product(product_id)

@app.route("/api/admin/upload-image", methods=["POST"])
def admin_upload_image():
    return admin_controller.admin_upload_image()

# Stock Management
@app.route("/api/admin/products/<int:product_id>/stock", methods=["PATCH"])
def admin_update_stock(product_id):
    return admin_controller.admin_update_stock(product_id)

# Categories Management
@app.route("/api/admin/categories", methods=["GET"])
def admin_get_categories():
    return admin_controller.admin_get_categories()

@app.route("/api/admin/categories", methods=["POST"])
def admin_create_category():
    return admin_controller.admin_create_category()

@app.route("/api/admin/categories/<int:category_id>", methods=["PUT"])
def admin_update_category(category_id):
    return admin_controller.admin_update_category(category_id)

@app.route("/api/admin/categories/<int:category_id>", methods=["DELETE"])
def admin_delete_category(category_id):
    return admin_controller.admin_delete_category(category_id)

# Enquiries & Tracking
@app.route("/api/admin/enquiries", methods=["GET"])
def admin_get_enquiries():
    return admin_controller.admin_get_enquiries()

@app.route("/api/admin/enquiries/<int:enquiry_id>", methods=["GET"])
def admin_get_enquiry_by_id(enquiry_id):
    return admin_controller.admin_get_enquiry_by_id(enquiry_id)

@app.route("/api/admin/enquiries/<int:enquiry_id>/status", methods=["PATCH"])
def admin_update_enquiry_status(enquiry_id):
    return admin_controller.admin_update_enquiry_status(enquiry_id)

@app.route("/api/admin/enquiries/<int:enquiry_id>/notes", methods=["POST"])
def admin_save_enquiry_note(enquiry_id):
    return admin_controller.admin_save_enquiry_note(enquiry_id)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
