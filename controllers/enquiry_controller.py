
from flask import jsonify, request

from dbConnection import get_db_connection


def create_enquiry():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Valid JSON body is required"}), 400

    required_fields = [
        "buyer_name", "email", "phone", "items"
    ]

    import re

    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"{field} is required"}), 400

    # Email format validation
    email_clean = str(data["email"]).strip()
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_regex, email_clean):
        return jsonify({"error": "Please enter a valid email address (e.g., name@company.com)"}), 400

    # Phone number length and format limitation: exactly 10 digits
    phone_digits = re.sub(r"\D", "", str(data["phone"]))
    if len(phone_digits) != 10:
        return jsonify({"error": "Phone number must be exactly 10 digits (e.g. 9876543210)"}), 400

    # Business legitimacy & anti-spam validation
    company_name = str(data.get("company_name", "")).strip()
    tax_id = str(data.get("tax_id", "")).strip()
    delivery_address = str(data.get("delivery_address", "")).strip()
    destination_port = str(data.get("destination_port", "")).strip()
    business_website = str(data.get("business_website", "")).strip()
    is_address_verified = bool(data.get("is_address_verified", False))

    if not company_name:
        return jsonify({"error": "Company name is required for commercial export quotation"}), 400

    if not tax_id:
        return jsonify({"error": "Business Tax ID / Trade License No. is required for trade verification"}), 400

    if len(tax_id) < 4:
        return jsonify({"error": "Please enter a valid Business Tax ID or Trade Registration Number (min 4 characters)"}), 400

    if not destination_port:
        return jsonify({"error": "Destination discharge port is required to calculate freight & logistics"}), 400

    if not delivery_address or len(delivery_address) < 5:
        return jsonify({"error": "Full company / warehouse delivery address is required"}), 400

    items = data["items"]

    if not isinstance(items, list) or not items:
        return jsonify({"error": "At least one product is required"}), 400

    for item in items:
        if not isinstance(item, dict):
            return jsonify({"error": "Invalid product item"}), 400

        if not item.get("product_id") or not item.get("quantity"):
            return jsonify({
                "error": "Each item needs product_id and quantity"
            }), 400

    connection = get_db_connection()

    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = connection.cursor()

        country = data.get("country") or data.get("buyer_country") or ""

        # Compose full details message for procedure storage
        full_message = data.get("message") or ""

        cursor.callproc("sp_save_enquiry", [
            data["buyer_name"],
            company_name,
            data.get("buyer_type", "other"),
            data["email"],
            data["phone"],
            country,
            full_message
        ])

        enquiry_id = None

        for result in cursor.stored_results():
            row = result.fetchone()
            if row:
                enquiry_id = row[0]

        if enquiry_id is None:
            raise Exception("Failed to create enquiry")

        # Generate Unique Reference ID & 6-Digit Secret PIN for Instant Tracking
        import secrets
        secret_pin = str(secrets.randbelow(900000) + 100000)
        reference_id = f"ENQ-2026-{enquiry_id:04d}"

        # Update newly added structured B2B verification fields, reference_id, and secret_pin
        update_query = """
            UPDATE enquiries
            SET destination_port = %s,
                delivery_address = %s,
                tax_id = %s,
                business_website = %s,
                verification_status = %s,
                is_address_verified = %s,
                reference_id = %s,
                secret_pin = %s
            WHERE id = %s
        """
        cursor.execute(update_query, [
            destination_port,
            delivery_address,
            tax_id,
            business_website,
            "pending_kyc",
            1 if is_address_verified else 0,
            reference_id,
            secret_pin,
            enquiry_id
        ])

        for item in items:
            cursor.callproc("sp_save_enquiry_item", [
                enquiry_id,
                item["product_id"],
                item["quantity"],
                item.get("unit", "kg"),
                item.get("packaging_requested")
            ])

            # Consume any result sets returned by the procedure.
            for result in cursor.stored_results():
                result.fetchall()

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Enquiry submitted successfully.",
            "enquiry_id": enquiry_id,
            "reference_id": reference_id,
            "secret_pin": secret_pin
        }), 201

    except Exception as e:
        connection.rollback()
        print(f"Error creating enquiry: {e}")
        return jsonify({
            "error": "Failed to submit enquiry. Please try again."
        }), 500

    finally:
        cursor.close()
        connection.close()


def track_enquiry_by_pin():
    data = request.get_json(silent=True) or {}
    reference_id = str(data.get("reference_id", "")).strip().upper()
    secret_pin = str(data.get("secret_pin", "")).strip()

    if not reference_id:
        return jsonify({"error": "Enquiry Reference ID is required (e.g. ENQ-2026-0001)."}), 400

    if not secret_pin:
        return jsonify({"error": "Secret PIN is required to view quotation status."}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database service unavailable. Please try again."}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        # Search by exact reference_id, case-insensitive, or numeric ID fallback
        numeric_id = reference_id.replace("ENQ-2026-", "").replace("IK-ENQ-", "").lstrip("0")
        try:
            parsed_id = int(numeric_id) if numeric_id else -1
        except ValueError:
            parsed_id = -1

        query = """
            SELECT * FROM enquiries 
            WHERE UPPER(reference_id) = %s 
               OR reference_id = %s
               OR id = %s
            LIMIT 1
        """
        cursor.execute(query, [reference_id, reference_id, parsed_id])
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": f"No quotation request found with Reference ID '{reference_id}'."}), 404

        # Validate secret PIN
        stored_pin = str(row.get("secret_pin", "")).strip()
        if stored_pin != secret_pin:
            return jsonify({"error": "Incorrect Secret PIN. Please check your PIN and try again."}), 401

        # Fetch product items
        cursor.execute(
            """
            SELECT 
                ei.id, ei.product_id, ei.quantity, ei.unit, ei.packaging_requested,
                p.name as product_name, p.product_code, p.category_id
            FROM enquiry_items ei
            LEFT JOIN products p ON ei.product_id = p.id
            WHERE ei.enquiry_id = %s
            """,
            [row["id"]]
        )
        items = cursor.fetchall()

        raw_status = row.get("verification_status") or row.get("status") or "pending"
        status_map = {
            "pending": {"label": "Request Received", "color": "#E5C378", "step": 1},
            "submitted": {"label": "Request Received", "color": "#E5C378", "step": 1},
            "under_review": {"label": "Under Review (Trade KYC)", "color": "#F39C12", "step": 2},
            "pending_kyc": {"label": "Under Review (Trade KYC)", "color": "#F39C12", "step": 2},
            "quote_sent": {"label": "Quotation Ready", "color": "#3498DB", "step": 3},
            "accepted": {"label": "Quotation Accepted", "color": "#2ECC71", "step": 4},
            "quote_accepted": {"label": "Quotation Accepted", "color": "#2ECC71", "step": 4},
            "order_confirmed": {"label": "Order Confirmed", "color": "#10B981", "step": 4},
            "processing": {"label": "Processing & Sortex Cleaning", "color": "#8B5CF6", "step": 5},
            "packed": {"label": "Packed in Export Bags", "color": "#F59E0B", "step": 6},
            "shipped": {"label": "Vessel Shipped (In Transit)", "color": "#06B6D4", "step": 7},
            "delivered": {"label": "Delivered at Port", "color": "#059669", "step": 8},
            "completed": {"label": "Delivered / Closed", "color": "#059669", "step": 8},
            "rejected": {"label": "Quotation Rejected", "color": "#E74C3C", "step": 0},
            "quote_rejected": {"label": "Quotation Rejected", "color": "#E74C3C", "step": 0},
            "cancelled": {"label": "Closed / Cancelled", "color": "#E74C3C", "step": 0}
        }
        status_meta = status_map.get(raw_status, {"label": raw_status.replace("_", " ").title(), "color": "#E5C378", "step": 1})

        # Fetch status audit history
        cursor.execute("""
            SELECT id, old_status, new_status, note, changed_by, created_at
            FROM enquiry_status_history
            WHERE enquiry_id = %s
            ORDER BY id ASC
        """, [row["id"]])
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

        enquiry_data = {
            "id": row["id"],
            "reference_id": row.get("reference_id") or f"ENQ-2026-{row['id']:04d}",
            "secret_pin": row.get("secret_pin", ""),
            "buyer_name": row["buyer_name"],
            "company_name": row["company_name"],
            "buyer_type": row["buyer_type"],
            "email": row["email"],
            "phone": row["phone"],
            "country": row["country"],
            "destination_port": row["destination_port"],
            "delivery_address": row["delivery_address"],
            "tax_id": row["tax_id"],
            "business_website": row.get("business_website"),
            "is_address_verified": bool(row.get("is_address_verified")),
            "status": raw_status,
            "status_label": status_meta["label"],
            "status_color": status_meta["color"],
            "step": status_meta["step"],
            "created_at": row["created_at"].strftime("%d %b %Y, %I:%M %p") if row.get("created_at") else "",
            "items": items,
            "history": history
        }

        return jsonify({
            "success": True,
            "enquiry": enquiry_data
        }), 200

    except Exception as e:
        print(f"Error in track_enquiry_by_pin: {e}")
        return jsonify({"error": "Failed to retrieve quotation details. Please try again."}), 500
    finally:
        conn.close()


def change_enquiry_pin():
    data = request.get_json(silent=True) or {}
    reference_id = str(data.get("reference_id", "")).strip().upper()
    current_pin = str(data.get("current_pin", "")).strip()
    new_pin = str(data.get("new_pin", "")).strip()

    if not reference_id:
        return jsonify({"error": "Reference ID is required."}), 400

    if not current_pin:
        return jsonify({"error": "Current Secret PIN is required."}), 400

    if not new_pin or len(new_pin) < 4:
        return jsonify({"error": "New Secret PIN must be at least 4 digits/characters."}), 400

    if current_pin == new_pin:
        return jsonify({"error": "New PIN cannot be the same as your current PIN."}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database service unavailable."}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, secret_pin FROM enquiries WHERE UPPER(reference_id) = %s LIMIT 1", [reference_id])
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": f"Quotation with Reference ID '{reference_id}' not found."}), 404

        stored_pin = str(row.get("secret_pin", "")).strip()
        if stored_pin != current_pin:
            return jsonify({"error": "Current Secret PIN is incorrect."}), 401

        cursor.execute("UPDATE enquiries SET secret_pin = %s WHERE id = %s", [new_pin, row["id"]])
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Secret PIN changed successfully! Please keep your new PIN safe.",
            "new_pin": new_pin
        }), 200

    except Exception as e:
        conn.rollback()
        print(f"Error in change_enquiry_pin: {e}")
        return jsonify({"error": "Failed to update Secret PIN. Please try again."}), 500
    finally:
        conn.close()

