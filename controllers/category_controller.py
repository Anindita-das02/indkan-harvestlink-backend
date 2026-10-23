
from flask import jsonify

from dbConnection import get_db_connection


def get_categories():
    connection = get_db_connection()

    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.callproc("sp_get_categories")

        categories = []

        for result in cursor.stored_results():
            categories = result.fetchall()

        cursor.close()

        return jsonify(categories), 200

    finally:
        connection.close()
