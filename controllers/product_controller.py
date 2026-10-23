
from flask import jsonify, request
from dbConnection import get_db_connection


def get_products():
    connection = get_db_connection()

    if connection is None:
        return jsonify({
            "status": "error",
            "message": "Database connection failed",
            "data": None
        }), 500

    try:
        category_id = request.args.get("category_id", type=int)

        cursor = connection.cursor(dictionary=True)
        cursor.callproc("sp_get_products", [category_id])

        products = []

        for result in cursor.stored_results():
            products = result.fetchall()

        cursor.close()

        return jsonify({
            "status": "success",
            "message": "Products fetched successfully",
            "data": products
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Failed to fetch products",
            "data": None
        }), 500

    finally:
        connection.close()


def get_product_by_id(product_id):
    connection = get_db_connection()

    if connection is None:
        return jsonify({
            "status": "error",
            "message": "Database connection failed",
            "data": None
        }), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.callproc("sp_get_product_by_id", [product_id])

        product = None

        for result in cursor.stored_results():
            product = result.fetchone()

        cursor.close()

        if product is None:
            return jsonify({
                "status": "error",
                "message": "Product not found",
                "data": None
            }), 404

        return jsonify({
            "status": "success",
            "message": "Product details fetched successfully",
            "data": product
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Failed to fetch product details",
            "data": None
        }), 500

    finally:
        connection.close()
