"""
CodeCraftHub - Course Tracking REST API

This Flask application provides CRUD operations for courses and stores
course data in a local JSON file called courses.json.

Run the application with:

    python app.py

The API will be available at:

    http://127.0.0.1:5000
"""

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request


# Create the Flask application
app = Flask(__name__)


# Store courses.json in the same folder as this app.py file
DATA_FILE = Path(__file__).parent / "courses.json"


# Allowed course status values
VALID_STATUSES = {
    "Not Started",
    "In Progress",
    "Completed",
}


class DataStoreError(Exception):
    """
    Custom exception for JSON file read and write problems.

    Creating a custom exception makes it easier to distinguish data-file
    errors from normal validation errors.
    """

    pass


def initialize_data_file():
    """
    Create courses.json automatically if it does not already exist.

    The file starts with an empty JSON list because courses will be stored
    as a list of course objects.
    """

    try:
        if not DATA_FILE.exists():
            DATA_FILE.write_text("[]", encoding="utf-8")
    except OSError as error:
        raise DataStoreError(
            f"Could not create the data file: {error}"
        ) from error


def load_courses():
    """
    Read and return all courses from courses.json.

    Returns:
        list: A list of course dictionaries.

    Raises:
        DataStoreError: If the file cannot be read or contains invalid JSON.
    """

    # Make sure the file exists before trying to read it
    initialize_data_file()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            courses = json.load(file)

    except OSError as error:
        raise DataStoreError(
            f"Could not read the data file: {error}"
        ) from error

    except json.JSONDecodeError as error:
        raise DataStoreError(
            "The data file contains invalid JSON."
        ) from error

    # The top-level JSON value should always be a list
    if not isinstance(courses, list):
        raise DataStoreError(
            "The data file must contain a JSON list."
        )

    return courses


def save_courses(courses):
    """
    Save all courses to courses.json.

    Args:
        courses: A list of course dictionaries.

    Raises:
        DataStoreError: If the file cannot be written.
    """

    try:
        with DATA_FILE.open("w", encoding="utf-8") as file:
            json.dump(courses, file, indent=4)

    except OSError as error:
        raise DataStoreError(
            f"Could not write to the data file: {error}"
        ) from error


def generate_course_id(courses):
    """
    Generate the next numeric course ID.

    IDs start at 1. The next ID is one greater than the current largest ID.
    This means deleted IDs will not be reused.

    Example:
        Existing IDs: 1, 2, 3
        New ID: 4
    """

    if not courses:
        return 1

    existing_ids = [
        course.get("id", 0)
        for course in courses
        if isinstance(course.get("id"), int)
    ]

    if not existing_ids:
        return 1

    return max(existing_ids) + 1


def get_course_by_id(courses, course_id):
    """
    Find one course by its numeric ID.

    Returns:
        dict or None: The matching course, or None if not found.
    """

    for course in courses:
        if course.get("id") == course_id:
            return course

    return None


def validate_course_data(data):
    """
    Validate the data sent by the client.

    All four course fields are required:
    - name
    - description
    - target_date
    - status

    Returns:
        str or None: An error message, or None when the data is valid.
    """

    # Make sure the request body is a JSON object
    if not isinstance(data, dict):
        return "Request body must be a JSON object."

    required_fields = [
        "name",
        "description",
        "target_date",
        "status",
    ]

    # Check that all required fields are present
    missing_fields = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing_fields:
        return (
            "Missing required fields: "
            + ", ".join(missing_fields)
        )

    # Name must be a non-empty string
    if not isinstance(data["name"], str) or not data["name"].strip():
        return "name must be a non-empty string."

    # Description must be a non-empty string
    if (
        not isinstance(data["description"], str)
        or not data["description"].strip()
    ):
        return "description must be a non-empty string."

    # target_date must be a string in exactly YYYY-MM-DD format
    target_date = data["target_date"]

    if not isinstance(target_date, str):
        return "target_date must be a string in YYYY-MM-DD format."

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date):
        return "target_date must use YYYY-MM-DD format."

    try:
        # This also catches invalid dates such as 2026-02-31
        date.fromisoformat(target_date)
    except ValueError:
        return "target_date must be a valid date."

    # Status must match one of the allowed values exactly
    if data["status"] not in VALID_STATUSES:
        return (
            "Invalid status. Status must be one of: "
            "'Not Started', 'In Progress', or 'Completed'."
        )

    return None


def current_timestamp():
    """
    Return the current UTC time as an ISO 8601 timestamp.

    Example:
        2026-09-28T12:30:45.123456+00:00
    """

    return datetime.now(timezone.utc).isoformat()


@app.errorhandler(DataStoreError)
def handle_data_store_error(error):
    """
    Return a helpful response when courses.json cannot be read or written.
    """

    return jsonify({
        "error": "Data file error",
        "message": str(error),
    }), 500


@app.errorhandler(500)
def handle_internal_error(error):
    """
    Handle unexpected server errors.

    This prevents Flask from returning an HTML error page to an API client.
    """

    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred.",
    }), 500


@app.route("/api/courses", methods=["POST"])
def create_course():
    """
    POST /api/courses

    Add a new course.
    """

    # Read JSON from the request body
    data = request.get_json(silent=True)

    # Validate all required course fields
    validation_error = validate_course_data(data)

    if validation_error:
        return jsonify({
            "error": validation_error,
        }), 400

    # Load existing courses from the JSON file
    courses = load_courses()

    # Create a new course object
    new_course = {
        "id": generate_course_id(courses),
        "name": data["name"].strip(),
        "description": data["description"].strip(),
        "target_date": data["target_date"],
        "status": data["status"],
        "created_at": current_timestamp(),
    }

    # Add the new course to the list and save it
    courses.append(new_course)
    save_courses(courses)

    return jsonify(new_course), 201


@app.route("/api/courses", methods=["GET"])
def get_all_courses():
    """
    GET /api/courses

    Return all courses.
    """

    courses = load_courses()

    return jsonify(courses), 200


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_single_course(course_id):
    """
    GET /api/courses/<id>

    Return one course by ID.
    """

    courses = load_courses()
    course = get_course_by_id(courses, course_id)

    if course is None:
        return jsonify({
            "error": "Course not found.",
        }), 404

    return jsonify(course), 200


@app.route("/api/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    """
    PUT /api/courses/<id>

    Replace the editable fields of an existing course.

    PUT requires all course fields:
    - name
    - description
    - target_date
    - status

    The ID and created_at timestamp cannot be changed.
    """

    # Read JSON from the request body
    data = request.get_json(silent=True)

    # Validate the complete course data
    validation_error = validate_course_data(data)

    if validation_error:
        return jsonify({
            "error": validation_error,
        }), 400

    courses = load_courses()
    course = get_course_by_id(courses, course_id)

    if course is None:
        return jsonify({
            "error": "Course not found.",
        }), 404

    # Update only editable fields
    course["name"] = data["name"].strip()
    course["description"] = data["description"].strip()
    course["target_date"] = data["target_date"]
    course["status"] = data["status"]

    # Save the updated list
    save_courses(courses)

    return jsonify(course), 200


@app.route("/api/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    """
    DELETE /api/courses/<id>

    Delete one course by ID.
    """

    courses = load_courses()
    course = get_course_by_id(courses, course_id)

    if course is None:
        return jsonify({
            "error": "Course not found.",
        }), 404

    # Remove the course from the list
    courses.remove(course)

    # Save the updated list
    save_courses(courses)

    return jsonify({
        "message": "Course deleted successfully.",
        "course": course,
    }), 200


if __name__ == "__main__":
    """
    This block runs only when this file is executed directly.

    The data file is also initialized here so courses.json is created
    immediately when the application starts.
    """

    initialize_data_file()

    # debug=True automatically reloads the app when code changes.
    # Turn debug=False when deploying to production.
    app.run(debug=True)