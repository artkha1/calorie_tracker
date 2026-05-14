import functools
import sqlite3

from flask import Blueprint, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from storage.database import get_user, create_user

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."

        if error is None:
            try:
                create_user(username, generate_password_hash(password))
                return redirect(url_for("main.index"))
            except sqlite3.IntegrityError:
                error = "Username already exists."
            except Exception:
                error = "Registration failed."

        if error:
            flash(error)
        return redirect(url_for("main.index", register=1))

    return redirect(url_for("main.index", register=1))


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "GET":
        return redirect(url_for("main.index", login=1))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        error = None

        user = get_user(username)

        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            session["username"] = user["username"]
            return redirect(url_for("main.index"))

        flash(error)
        return redirect(url_for("main.index", login=1))

    return redirect(url_for("main.index", login=1))


@bp.before_app_request
def load_logged_in_user():
    name = session.get("username")
    g.user = get_user(name) if name else None


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("main.index", login=1))
        return view(**kwargs)

    return wrapped_view