import functools

from flask import Blueprint, flash, g, redirect, request, session, url_for
from postgrest.exceptions import APIError
from werkzeug.security import check_password_hash, generate_password_hash

from storage.database import get_supabase

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
            sb = get_supabase()
            try:
                sb.table("users").insert(
                    {
                        "username": username,
                        "password": generate_password_hash(password),
                    }
                ).execute()
                return redirect(url_for("index"))
            except APIError as e:
                msg = str(e).lower()
                if "duplicate" in msg or "unique" in msg or "23505" in msg:
                    error = "Username already exists."
                else:
                    error = "Registration failed."

        if error:
            flash(error)
        return redirect(url_for("index", register=1))

    return redirect(url_for("index", register=1))


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "GET":
        return redirect(url_for("index", login=1))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        error = None

        sb = get_supabase()
        res = (
            sb.table("users")
            .select("username, password")
            .eq("username", username)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        user = rows[0] if rows else None

        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            # Session keyed by username — Supabase schema may not have users.id
            session["username"] = user["username"]
            return redirect(url_for("index"))

        flash(error)
        return redirect(url_for("index", login=1))

    return redirect(url_for("index", login=1))


@bp.before_app_request
def load_logged_in_user():
    name = session.get("username")
    if name is None:
        g.user = None
    else:
        sb = get_supabase()
        res = (
            sb.table("users")
            .select("*")
            .eq("username", name)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        g.user = rows[0] if rows else None


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("index", login=1))
        return view(**kwargs)

    return wrapped_view
