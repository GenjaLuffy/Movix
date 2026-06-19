import mysql.connector
from mysql.connector import Error


def get_connection():
    """
    Create and return a MySQL database connection.
    Make sure to update credentials below.
    """

    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",          # change if needed
            password="",          # put your MySQL password
            database="movix"      # your DB name
        )

        if conn.is_connected():
            return conn

    except Error as e:
        print("Database connection error:", e)
        return None


# ---------------------------------------------------
# OPTIONAL: helper to always get dictionary cursor
# ---------------------------------------------------
def get_cursor(conn):
    """
    Returns dictionary cursor so you can do:
    row["title"] instead of row[0]
    """
    return conn.cursor(dictionary=True)