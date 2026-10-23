
from flask import jsonify, request

from dbConnection import get_db_connection


def create_enquiry():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Valid JSON body is required"}), 400

    required_fields = [
        "buyer_name", "email", "phone", "items"
    ]

    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"{field} is required"}), 400

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

        cursor.callproc("sp_save_enquiry", [
            data["buyer_name"],
            data.get("company_name"),
            data.get("buyer_type", "other"),
            data["email"],
            data["phone"],
            data.get("message")
        ])

        enquiry_id = None

        for result in cursor.stored_results():
            row = result.fetchone()
            if row:
                enquiry_id = row[0]

        if enquiry_id is None:
            raise Exception("Failed to create enquiry")

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
            "enquiry_id": enquiry_id
        }), 201

    except Exception:
        connection.rollback()
        return jsonify({
            "error": "Failed to submit enquiry. Please try again."
        }), 500

    finally:
        cursor.close()
        connection.close()
