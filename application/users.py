import functools
import re
from typing import Any, Dict, Final, List, Literal, Optional

from flask import Blueprint, Response, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from application.db import get_db, log

username_regex: Final[str] = "[^0-9a-zA-Z]+"
bp = Blueprint("users", __name__, url_prefix="/users")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("users.login"))

        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session["admin"] == 0:
            flash("Administrator login required!")
            return redirect(url_for("users.settings"))

        return view(**kwargs)

    return wrapped_view


# defines the index page
@bp.route("/", methods=["GET", "POST"])
@login_required
@admin_required  # only admins can view userlist
def index():
    if request.method == "POST":  # register user
        username = request.form["username"].capitalize()
        password = request.form["password"]
        privilege = request.form["privilege"]
        db = get_db()
        error = None

        # ensures no special characters are present in username, should prevent injection attacks
        if re.compile("username_regex").search(username) or len(username) > 20:
            error = "Invalid Username"
        elif not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif not privilege:
            error = "Privilege is required."

        if privilege == "admin":
            admin = 1
        else:
            admin = 0

        if error is None:
            try:
                db.execute("INSERT INTO user (username, admin, password) VALUES (?, ?, ?)", (username, admin, generate_password_hash(password)))
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                session.clear()
                return redirect(url_for("users.login"))

        if error is not None:
            flash(error)

    return render_template("users/list.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"].capitalize()
        password = request.form["password"]
        db = get_db()
        error = None
        user = db.execute("SELECT * FROM user WHERE username = ?", (username,)).fetchone()

        if re.compile("username_regex").search(username):  # ensures no special characters are present in username, should prevent injection attacks
            error = "Invalid Username"
        elif user is None:
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            log("INFO", "Logging in user " + username.lower())
            session.clear()
            session["user_id"] = user["id"]
            session["admin"] = user["admin"]
            return redirect(url_for("index"))
        else:
            log("WARN", "Failed login - user " + username.lower() + ": " + error)
            flash(error)

    return render_template("users/login.html")


@bp.route("/settings", methods=("GET", "POST"))
@login_required
def user():
    if request.method == "POST":
        db = get_db()
        user_id = session["user_id"]
        error = None
        if "change_password" in request.form:
            old_password = request.form["old_password"]
            new_password = request.form["new_password"]
            if not old_password or not new_password:  # check that the form is complete
                error = "All fields are required."

            user_data = db.execute(
                "SELECT * FROM user WHERE id = {}".format(
                    user_id,
                )
            ).fetchone()  # grab user data to check old password

            if user_data is None:  # catch database errors
                error = "Database error."
            elif not check_password_hash(user_data["password"], old_password):  # check that the old password is correct
                error = "Incorrect password."

            log("INFO", "User " + user_data["username"].lower() + " changed their password")
            db.execute("UPDATE user SET password = '{}' WHERE id = '{}'".format(generate_password_hash(new_password), user_id))  # update password
            db.commit()
        elif "change_username" in request.form:
            password = request.form["password"]
            new_username = request.form["new_username"].capitalize()

            if not password or not new_username:  # check that the form is complete
                error = "All fields are required."

            user_data = db.execute("SELECT * FROM user WHERE id = {}".format(user_id)).fetchone()  # grab user data to check password

            # ensures no special characters are present in username, should prevent injection attacks
            if re.compile("username_regex").search(new_username) or len(new_username) > 20:
                error = "Invalid New Username"
            elif user_data is None:  # catch database errors
                error = "Database error."
            elif not check_password_hash(user_data["password"], password):  # check that the password is correct
                error = "Incorrect password."

            log("INFO", "User " + user_data["username"].lower() + " changed their username to " + new_username.lower())
            db.execute("UPDATE user SET username = '{}' WHERE id = '{}'".format(new_username, user_id))  # update username
            db.commit()
        if error is not None:
            flash(error)

    return render_template("users/settings.html")


# defines a users function which is called when /get-users is accessed
@bp.route("/get-users", methods=["GET"])
@login_required
@admin_required
def get_users():
    db = get_db()
    return jsonify(
        [
            {"id": user["id"], "username": user["username"], "role": "Admin" if user["admin"] == 1 else "User"}
            for user in db.execute("SELECT * FROM user")
        ]
    )


# delete user route
@login_required
@admin_required
@bp.route("<string:username>", methods=["DELETE"])
def delete_user(username: str) -> Response:
    """
    Route to delete a user. Only admins can access this route.

    Parameters:
    ----------
    username : str
        The username of the user to delete.
    """
    db = get_db()

    deleting_admin = db.execute("SELECT admin FROM user WHERE username = ?", (username,)).fetchone()["admin"]
    admin_users: Final[List[Any]] = db.execute("SELECT * FROM user WHERE admin = 1").fetchall()
    if deleting_admin and len(admin_users) == 1:
        return Response(status=403)  # cannot delete last admin

    log("INFO", f"Admin {g.user['username'].lower()} deleted {username}'s account!")
    db.execute(f"DELETE FROM user WHERE username = '{username}'")
    db.commit()

    return Response(status=200)


# change role route
@login_required
@admin_required
@bp.route("<string:username>/<string:action>", methods=["POST"])
def modify_user(username: str, action: Literal["promote", "demote", "reset-password"]):
    """
    Route to promote, demote, or reset password of a user. Only admins can access this route.

    Parameters:
    ----------
    username : str
        The username of the user to modify.
    action : Literal["promote", "demote", "reset-password"]
        The action to perform on the user.
    """
    db = get_db()

    current_user: Final[str] = g.user["username"].lower()

    if action == "reset-password":
        data: Dict[str, Any] = request.get_json()
        password: Optional[str] = data.get("password")

        if not password:
            return Response(status=400)

        log("INFO", f"Admin {current_user} changed {username}'s password.")
        db.execute(f"UPDATE user SET password = '{generate_password_hash(password)}' WHERE username = '{username}'")  # update password
        db.commit()

    else:
        promote: Final[bool] = True if action == "promote" else False
        new_role: Final[Literal["Admin", "User"]] = "Admin" if promote else "User"

        user_data = db.execute("SELECT * FROM user WHERE admin = 1").fetchall()
        if not promote and len(user_data) == 1:
            return Response(status=403)  # cannot demote last admin

        log("INFO", f"Admin {current_user} {action}d {username}'s role to {new_role}.")
        if promote:
            db.execute(f"UPDATE user SET admin = 1 WHERE username = '{username}'")
        else:
            db.execute(f"UPDATE user SET admin = 0 WHERE username = '{username}'")
        db.commit()

    return Response(status=200)
