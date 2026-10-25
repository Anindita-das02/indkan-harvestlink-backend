import os
import re
import time
import json
import base64
import hmac
import hashlib
import uuid
from datetime import datetime
from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from dbConnection import get_db_connection

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
SECRET_KEY = os.getenv("SECRET_KEY", "indkan-harvestlink-b2b-secret-trade-key-2026").encode("utf-8")

def _generate_admin_token(user_id: int, email: str, name: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + (7 * 24 * 3600)  # 7 days
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    sig = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def _verify_admin_token(token: str):
    try:
        if not token or "." not in token:
            return None
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(SECRET_KEY, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_b64.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        if payload.get("role") != "admin":
            return None
        return payload
    except Exception:
        return None

def _get_auth_admin():
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif request.args.get("token"):
        token = request.args.get("token").strip()
    return _verify_admin_token(token)

# =========================================================================
# 1. ADMIN AUTHENTICATION
# =========================================================================

def admin_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed."}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = %s AND is_active = 1 LIMIT 1", [email])
        user = cursor.fetchone()

        if not user or user.get("role") != "admin":
            return jsonify({"error": "Invalid admin credentials."}), 401

        if not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Incorrect password."}), 401

        token = _generate_admin_token(user["id"], user["email"], user["name"])

        return jsonify({
            "success": True,
            "message": "Admin authenticated successfully.",
            "token": token,
            "admin": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200
    except Exception as e:
        print(f"Error in admin_login: {e}")
        return jsonify({"error": "Login failed. Please try again."}), 500
    finally:
        conn.close()

def get_admin_profile():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized admin access."}), 401
    return jsonify({"success": True, "admin": admin}), 200

def admin_change_password():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    current_pw = str(data.get("current_password", "")).strip()
    new_pw = str(data.get("new_password", "")).strip()

    if not current_pw or not new_pw:
        return jsonify({"error": "Current and new password are required."}), 400
    if len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", [admin["user_id"]])
        user = cursor.fetchone()
        if not user or not check_password_hash(user["password_hash"], current_pw):
            return jsonify({"error": "Current password does not match."}), 400

        new_hash = generate_password_hash(new_pw)
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", [new_hash, admin["user_id"]])
        conn.commit()
        return jsonify({"success": True, "message": "Password updated successfully."}), 200
    finally:
        conn.close()

# =========================================================================
# 2. DASHBOARD KPI & ANALYTICS
# =========================================================================

def get_dashboard_stats():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database error."}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # Products stats
        cursor.execute("SELECT COUNT(*) as total FROM products WHERE is_active = 1")
        total_products = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as in_stock FROM products WHERE availability_status = 'in_stock' AND is_active = 1")
        in_stock_products = cursor.fetchone()["in_stock"]

        cursor.execute("SELECT COUNT(*) as low_stock FROM products WHERE availability_status = 'low_stock' AND is_active = 1")
        low_stock_products = cursor.fetchone()["low_stock"]

        cursor.execute("SELECT COUNT(*) as out_of_stock FROM products WHERE availability_status = 'out_of_stock' AND is_active = 1")
        out_of_stock_products = cursor.fetchone()["out_of_stock"]

        cursor.execute("SELECT COUNT(*) as on_request FROM products WHERE availability_status = 'on_request' AND is_active = 1")
        on_request_products = cursor.fetchone()["on_request"]

        # Enquiries stats
        cursor.execute("SELECT COUNT(*) as total FROM enquiries")
        total_enquiries = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as pending FROM enquiries WHERE status = 'pending' OR verification_status IN ('pending', 'submitted')")
        pending_enquiries = cursor.fetchone()["pending"]

        cursor.execute("SELECT COUNT(*) as under_review FROM enquiries WHERE status = 'pending_kyc' OR verification_status IN ('pending_kyc', 'under_review')")
        under_review_enquiries = cursor.fetchone()["under_review"]

        cursor.execute("SELECT COUNT(*) as quote_sent FROM enquiries WHERE status = 'quote_sent' OR verification_status = 'quote_sent'")
        quote_sent_enquiries = cursor.fetchone()["quote_sent"]

        cursor.execute("SELECT COUNT(*) as order_confirmed FROM enquiries WHERE verification_status IN ('accepted', 'quote_accepted', 'order_confirmed')")
        order_confirmed_enquiries = cursor.fetchone()["order_confirmed"]

        cursor.execute("SELECT COUNT(*) as in_shipment FROM enquiries WHERE verification_status IN ('processing', 'packed', 'shipped')")
        in_shipment_enquiries = cursor.fetchone()["in_shipment"]

        cursor.execute("SELECT COUNT(*) as completed FROM enquiries WHERE status = 'completed' OR verification_status IN ('completed', 'delivered')")
        completed_enquiries = cursor.fetchone()["completed"]

        # Recent 5 enquiries
        cursor.execute("""
            SELECT id, reference_id, buyer_name, company_name, email, phone, country, status, verification_status, created_at
            FROM enquiries
            ORDER BY id DESC LIMIT 6
        """)
        recent_enquiries_raw = cursor.fetchall()
        recent_enquiries = []
        for r in recent_enquiries_raw:
            recent_enquiries.append({
                "id": r["id"],
                "reference_id": r.get("reference_id") or f"ENQ-2026-{r['id']:04d}",
                "buyer_name": r["buyer_name"],
                "company_name": r["company_name"],
                "email": r["email"],
                "phone": r["phone"],
                "country": r["country"],
                "status": r.get("verification_status") or r.get("status") or "pending",
                "created_at": r["created_at"].strftime("%d %b %Y, %I:%M %p") if r.get("created_at") else ""
            })

        # Recent status history
        cursor.execute("""
            SELECT h.*, e.reference_id, e.buyer_name
            FROM enquiry_status_history h
            LEFT JOIN enquiries e ON h.enquiry_id = e.id
            ORDER BY h.id DESC LIMIT 6
        """)
        history_raw = cursor.fetchall()
        recent_history = []
        for h in history_raw:
            recent_history.append({
                "id": h["id"],
                "enquiry_id": h["enquiry_id"],
                "reference_id": h.get("reference_id") or f"ENQ-2026-{h['enquiry_id']:04d}",
                "buyer_name": h.get("buyer_name") or "Buyer",
                "old_status": h.get("old_status") or "",
                "new_status": h.get("new_status") or "",
                "note": h.get("note") or "",
                "changed_by": h.get("changed_by") or "Admin",
                "created_at": h["created_at"].strftime("%d %b %Y, %I:%M %p") if h.get("created_at") else ""
            })

        return jsonify({
            "success": True,
            "stats": {
                "total_products": total_products,
                "in_stock_products": in_stock_products,
                "low_stock_products": low_stock_products,
                "out_of_stock_products": out_of_stock_products,
                "on_request_products": on_request_products,
                "total_enquiries": total_enquiries,
                "pending_enquiries": pending_enquiries,
                "under_review_enquiries": under_review_enquiries,
                "quote_sent_enquiries": quote_sent_enquiries,
                "order_confirmed_enquiries": order_confirmed_enquiries,
                "in_shipment_enquiries": in_shipment_enquiries,
                "completed_enquiries": completed_enquiries,
            },
            "recent_enquiries": recent_enquiries,
            "recent_history": recent_history
        }), 200
    finally:
        conn.close()

# =========================================================================
# 3. PRODUCT MANAGEMENT
# =========================================================================

def admin_get_products():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.id DESC
        """)
        rows = cursor.fetchall()
        products = []
        for r in rows:
            # Parse packaging_options if json/str
            pkg = r.get("packaging_options")
            if isinstance(pkg, str):
                try:
                    pkg = json.loads(pkg)
                except Exception:
                    pkg = [pkg]
            products.append({
                "id": r["id"],
                "category_id": r["category_id"],
                "category_name": r.get("category_name") or "Commodity",
                "product_code": r.get("product_code") or "",
                "name": r["name"],
                "slug": r.get("slug") or "",
                "short_description": r.get("short_description") or "",
                "description": r.get("description") or "",
                "origin_country": r.get("origin_country") or "India",
                "quality_grade": r.get("quality_grade") or "Grade A Export",
                "minimum_order_quantity": float(r["minimum_order_quantity"]) if r.get("minimum_order_quantity") else 1.0,
                "moq_unit": r.get("moq_unit") or "Metric Ton",
                "stock_quantity": float(r["stock_quantity"]) if r.get("stock_quantity") is not None else 0.0,
                "stock_unit": r.get("stock_unit") or "Metric Ton",
                "availability_status": r.get("availability_status") or "in_stock",
                "packaging_options": pkg,
                "image_url": r.get("image_url") or "",
                "is_active": bool(r.get("is_active", 1)),
                "created_at": r["created_at"].strftime("%d %b %Y") if r.get("created_at") else ""
            })
        return jsonify({"success": True, "products": products}), 200
    finally:
        conn.close()

def admin_create_product():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    category_id = data.get("category_id")

    if not name or not category_id:
        return jsonify({"error": "Product name and category are required."}), 400

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    product_code = str(data.get("product_code", "")).strip() or f"IK-EXP-{int(time.time()) % 10000}"
    short_desc = str(data.get("short_description", "")).strip()
    desc = str(data.get("description", "")).strip()
    origin = str(data.get("origin_country", "India")).strip()
    grade = str(data.get("quality_grade", "Grade A Export")).strip()
    moq = float(data.get("minimum_order_quantity", 1.0))
    moq_unit = str(data.get("moq_unit", "Metric Ton")).strip()
    stock_qty = float(data.get("stock_quantity", 100.0))
    stock_unit = str(data.get("stock_unit", "Metric Ton")).strip()
    availability = str(data.get("availability_status", "in_stock")).strip()
    image_url = str(data.get("image_url", "")).strip()
    packaging = data.get("packaging_options")
    if isinstance(packaging, list):
        packaging = json.dumps(packaging)
    else:
        packaging = json.dumps(["25 kg bag", "50 kg PP bag", "Bulk Container Liner"])

    is_active = 1 if data.get("is_active", True) else 0

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO products (
                category_id, product_code, name, slug, short_description, description,
                origin_country, quality_grade, minimum_order_quantity, moq_unit,
                stock_quantity, stock_unit, availability_status, packaging_options,
                image_url, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, [
            category_id, product_code, name, slug, short_desc, desc,
            origin, grade, moq, moq_unit, stock_qty, stock_unit, availability,
            packaging, image_url, is_active
        ])
        conn.commit()
        new_id = cursor.lastrowid
        return jsonify({"success": True, "message": "Product created successfully.", "product_id": new_id}), 201
    except Exception as e:
        conn.rollback()
        print(f"Error admin_create_product: {e}")
        return jsonify({"error": "Failed to create product."}), 500
    finally:
        conn.close()

def admin_update_product(product_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Product name is required."}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        packaging = data.get("packaging_options")
        if isinstance(packaging, list):
            packaging = json.dumps(packaging)
        elif not packaging:
            packaging = json.dumps(["25 kg bag", "50 kg PP bag"])

        query = """
            UPDATE products SET
                category_id = %s,
                product_code = %s,
                name = %s,
                short_description = %s,
                description = %s,
                origin_country = %s,
                quality_grade = %s,
                minimum_order_quantity = %s,
                moq_unit = %s,
                stock_quantity = %s,
                stock_unit = %s,
                availability_status = %s,
                packaging_options = %s,
                image_url = %s,
                is_active = %s
            WHERE id = %s
        """
        cursor.execute(query, [
            data.get("category_id"),
            data.get("product_code", ""),
            name,
            data.get("short_description", ""),
            data.get("description", ""),
            data.get("origin_country", "India"),
            data.get("quality_grade", "Grade A Export"),
            float(data.get("minimum_order_quantity", 1.0)),
            data.get("moq_unit", "Metric Ton"),
            float(data.get("stock_quantity", 0.0)),
            data.get("stock_unit", "Metric Ton"),
            data.get("availability_status", "in_stock"),
            packaging,
            data.get("image_url", ""),
            1 if data.get("is_active", True) else 0,
            product_id
        ])
        conn.commit()
        return jsonify({"success": True, "message": "Product updated successfully."}), 200
    except Exception as e:
        conn.rollback()
        print(f"Error admin_update_product: {e}")
        return jsonify({"error": "Failed to update product."}), 500
    finally:
        conn.close()

def admin_toggle_product_status(product_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, is_active FROM products WHERE id = %s", [product_id])
        p = cursor.fetchone()
        if not p:
            return jsonify({"error": "Product not found."}), 404
        new_status = 0 if p["is_active"] == 1 else 1
        cursor.execute("UPDATE products SET is_active = %s WHERE id = %s", [new_status, product_id])
        conn.commit()
        return jsonify({"success": True, "message": "Product status updated.", "is_active": bool(new_status)}), 200
    finally:
        conn.close()

def admin_delete_product(product_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = %s", [product_id])
        conn.commit()
        return jsonify({"success": True, "message": "Product deleted successfully."}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Cannot delete product (may be linked to enquiries). Try deactivating it."}), 400
    finally:
        conn.close()

# =========================================================================
# 4. STOCK & AVAILABILITY MANAGEMENT
# =========================================================================

def admin_update_stock(product_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database error."}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, availability_status, stock_quantity, stock_unit FROM products WHERE id = %s", [product_id])
        current_prod = cursor.fetchone()
        if not current_prod:
            return jsonify({"error": "Product not found."}), 404

        availability = str(data.get("availability_status", current_prod["availability_status"])).strip().lower()
        stock_qty = float(data.get("stock_quantity", current_prod["stock_quantity"] if current_prod["stock_quantity"] is not None else 0.0))
        stock_unit = str(data.get("stock_unit", current_prod["stock_unit"] or "Metric Ton")).strip()

        valid_statuses = ["in_stock", "low_stock", "out_of_stock", "on_request"]
        if availability not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400

        cursor.execute("""
            UPDATE products 
            SET availability_status = %s, stock_quantity = %s, stock_unit = %s 
            WHERE id = %s
        """, [availability, stock_qty, stock_unit, product_id])
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Stock and availability updated successfully.",
            "availability_status": availability,
            "stock_quantity": stock_qty,
            "stock_unit": stock_unit
        }), 200
    finally:
        conn.close()

# =========================================================================
# 5. CATEGORY MANAGEMENT
# =========================================================================

def admin_get_categories():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*, COUNT(p.id) as product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id
            ORDER BY c.id ASC
        """)
        categories = cursor.fetchall()
        return jsonify({"success": True, "categories": categories}), 200
    finally:
        conn.close()

def admin_create_category():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    description = str(data.get("description", "")).strip()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO categories (name, slug, description, is_active) VALUES (%s, %s, %s, 1)", [name, slug, description])
        conn.commit()
        return jsonify({"success": True, "message": "Category created successfully.", "id": cursor.lastrowid}), 201
    finally:
        conn.close()

def admin_update_category(category_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    description = str(data.get("description", "")).strip()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE categories SET name = %s, description = %s WHERE id = %s", [name, description, category_id])
        conn.commit()
        return jsonify({"success": True, "message": "Category updated successfully."}), 200
    finally:
        conn.close()

def admin_delete_category(category_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = %s", [category_id])
        conn.commit()
        return jsonify({"success": True, "message": "Category deleted successfully."}), 200
    except Exception:
        return jsonify({"error": "Cannot delete category with associated products."}), 400
    finally:
        conn.close()

# =========================================================================
# 6. ENQUIRY MANAGEMENT & STATUS TRACKING
# =========================================================================

def admin_get_enquiries():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM enquiries
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        enquiries = []

        status_map = {
            "pending": {"label": "Submitted", "color": "#E5C378", "step": 1},
            "submitted": {"label": "Submitted", "color": "#E5C378", "step": 1},
            "under_review": {"label": "Under Review", "color": "#F39C12", "step": 2},
            "pending_kyc": {"label": "Under Review", "color": "#F39C12", "step": 2},
            "quote_sent": {"label": "Quotation Sent", "color": "#3498DB", "step": 3},
            "accepted": {"label": "Quotation Accepted", "color": "#2ECC71", "step": 4},
            "quote_accepted": {"label": "Quotation Accepted", "color": "#2ECC71", "step": 4},
            "rejected": {"label": "Quotation Rejected", "color": "#E74C3C", "step": 0},
            "quote_rejected": {"label": "Quotation Rejected", "color": "#E74C3C", "step": 0},
            "order_confirmed": {"label": "Order Confirmed", "color": "#10B981", "step": 4},
            "processing": {"label": "Processing (Sortex & Grading)", "color": "#8B5CF6", "step": 5},
            "packed": {"label": "Packed (Container Bags)", "color": "#F59E0B", "step": 6},
            "shipped": {"label": "Shipped (In Transit)", "color": "#06B6D4", "step": 7},
            "delivered": {"label": "Delivered", "color": "#059669", "step": 8},
            "completed": {"label": "Delivered / Closed", "color": "#059669", "step": 8},
            "cancelled": {"label": "Closed / Cancelled", "color": "#E74C3C", "step": 0}
        }

        for r in rows:
            # fetch items
            cursor.execute("""
                SELECT ei.*, p.name as product_name, p.product_code
                FROM enquiry_items ei
                LEFT JOIN products p ON ei.product_id = p.id
                WHERE ei.enquiry_id = %s
            """, [r["id"]])
            items = cursor.fetchall()

            raw_status = r.get("verification_status") or r.get("status") or "pending"
            meta = status_map.get(raw_status, {"label": raw_status.replace("_", " ").title(), "color": "#E5C378", "step": 1})

            enquiries.append({
                "id": r["id"],
                "reference_id": r.get("reference_id") or f"ENQ-2026-{r['id']:04d}",
                "secret_pin": r.get("secret_pin", ""),
                "buyer_name": r["buyer_name"],
                "company_name": r["company_name"],
                "buyer_type": r["buyer_type"],
                "email": r["email"],
                "phone": r["phone"],
                "country": r["country"],
                "destination_port": r.get("destination_port") or "",
                "delivery_address": r.get("delivery_address") or "",
                "tax_id": r.get("tax_id") or "",
                "business_website": r.get("business_website") or "",
                "is_address_verified": bool(r.get("is_address_verified")),
                "status": raw_status,
                "status_label": meta["label"],
                "status_color": meta["color"],
                "step": meta["step"],
                "admin_notes": r.get("admin_notes") or "",
                "created_at": r["created_at"].strftime("%d %b %Y, %I:%M %p") if r.get("created_at") else "",
                "items": items
            })

        return jsonify({"success": True, "enquiries": enquiries}), 200
    finally:
        conn.close()

def admin_get_enquiry_by_id(enquiry_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM enquiries WHERE id = %s LIMIT 1", [enquiry_id])
        r = cursor.fetchone()
        if not r:
            return jsonify({"error": "Enquiry not found."}), 404

        cursor.execute("""
            SELECT ei.*, p.name as product_name, p.product_code
            FROM enquiry_items ei
            LEFT JOIN products p ON ei.product_id = p.id
            WHERE ei.enquiry_id = %s
        """, [enquiry_id])
        items = cursor.fetchall()

        cursor.execute("""
            SELECT * FROM enquiry_status_history
            WHERE enquiry_id = %s
            ORDER BY id ASC
        """, [enquiry_id])
        history_raw = cursor.fetchall()
        history = []
        for h in history_raw:
            history.append({
                "id": h["id"],
                "old_status": h["old_status"],
                "new_status": h["new_status"],
                "note": h.get("note") or "",
                "changed_by": h.get("changed_by") or "Admin",
                "created_at": h["created_at"].strftime("%d %b %Y, %I:%M %p") if h.get("created_at") else ""
            })

        raw_status = r.get("verification_status") or r.get("status") or "pending"

        return jsonify({
            "success": True,
            "enquiry": {
                "id": r["id"],
                "reference_id": r.get("reference_id") or f"ENQ-2026-{r['id']:04d}",
                "secret_pin": r.get("secret_pin", ""),
                "buyer_name": r["buyer_name"],
                "company_name": r["company_name"],
                "buyer_type": r["buyer_type"],
                "email": r["email"],
                "phone": r["phone"],
                "country": r["country"],
                "destination_port": r.get("destination_port") or "",
                "delivery_address": r.get("delivery_address") or "",
                "tax_id": r.get("tax_id") or "",
                "business_website": r.get("business_website") or "",
                "is_address_verified": bool(r.get("is_address_verified")),
                "status": raw_status,
                "admin_notes": r.get("admin_notes") or "",
                "created_at": r["created_at"].strftime("%d %b %Y, %I:%M %p") if r.get("created_at") else "",
                "items": items,
                "history": history
            }
        }), 200
    finally:
        conn.close()

def admin_update_enquiry_status(enquiry_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip().lower()
    note = str(data.get("note", "")).strip()

    valid_statuses = [
        "pending", "submitted",
        "under_review", "pending_kyc",
        "quote_sent",
        "accepted", "quote_accepted",
        "rejected", "quote_rejected",
        "order_confirmed",
        "processing",
        "packed",
        "shipped",
        "delivered",
        "completed",
        "cancelled"
    ]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status '{new_status}'. Allowed: {', '.join(valid_statuses)}"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, status, verification_status, reference_id FROM enquiries WHERE id = %s", [enquiry_id])
        enq = cursor.fetchone()
        if not enq:
            return jsonify({"error": "Enquiry not found."}), 404

        old_status = enq.get("verification_status") or enq.get("status") or "pending"

        # Determine enum status for legacy column
        if new_status in ("delivered", "completed"):
            enum_status = "completed"
        elif new_status in ("rejected", "quote_rejected", "cancelled"):
            enum_status = "cancelled"
        elif new_status in ("order_confirmed", "processing", "packed", "shipped", "quote_sent", "accepted", "quote_accepted"):
            enum_status = "contacted"
        else:
            enum_status = "pending"

        # Update enquiry status in enquiries table
        cursor.execute("""
            UPDATE enquiries
            SET status = %s,
                verification_status = %s,
                status_updated_at = NOW(),
                status_updated_by = %s
            WHERE id = %s
        """, [
            enum_status,
            new_status,
            admin["user_id"],
            enquiry_id
        ])

        # Add history log
        cursor.execute("""
            INSERT INTO enquiry_status_history (enquiry_id, old_status, new_status, note, changed_by)
            VALUES (%s, %s, %s, %s, %s)
        """, [enquiry_id, old_status, new_status, note, admin["name"]])

        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Status updated to '{new_status}'. Live on buyer's Track Enquiry page.",
            "enquiry_id": enquiry_id,
            "new_status": new_status
        }), 200
    except Exception as e:
        conn.rollback()
        print(f"Error admin_update_enquiry_status: {e}")
        return jsonify({"error": "Failed to update status."}), 500
    finally:
        conn.close()

def admin_save_enquiry_note(enquiry_id: int):
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    data = request.get_json(silent=True) or {}
    admin_notes = str(data.get("admin_notes", "")).strip()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE enquiries SET admin_notes = %s WHERE id = %s", [admin_notes, enquiry_id])
        conn.commit()
        return jsonify({"success": True, "message": "Admin internal notes saved."}), 200
    finally:
        conn.close()

def admin_upload_image():
    admin = _get_auth_admin()
    if not admin:
        return jsonify({"error": "Unauthorized."}), 401

    if "image" not in request.files and "file" not in request.files:
        return jsonify({"error": "No image file provided in request."}), 400

    file = request.files.get("image") or request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename."}), 400

    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg"}
    original_filename = file.filename
    _, ext = os.path.splitext(original_filename.lower())
    if ext not in allowed_exts:
        return jsonify({"error": f"Invalid image format ({ext}). Allowed formats: JPG, PNG, WEBP, GIF, AVIF, SVG"}), 400

    products_dir = os.path.join(UPLOAD_FOLDER, "products")
    os.makedirs(products_dir, exist_ok=True)

    clean_base = re.sub(r"[^a-zA-Z0-9_-]+", "_", os.path.splitext(original_filename)[0])[:30].strip("_")
    unique_name = f"prod_{int(time.time())}_{clean_base}_{uuid.uuid4().hex[:6]}{ext}"
    dest_path = os.path.join(products_dir, unique_name)

    file.save(dest_path)

    image_url = f"/uploads/products/{unique_name}"
    return jsonify({
        "success": True,
        "message": "Image uploaded successfully from device.",
        "image_url": image_url,
        "filename": unique_name
    }), 200
