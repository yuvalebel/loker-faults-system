"""
Google OAuth login with email allowlist.

Usage in flask_app.py:
    from auth import init_auth, login_required

    init_auth(app)

    @app.route('/some-route')
    @login_required
    def some_route():
        ...

The decorator is also applied automatically to most routes via a
before_request hook below — see `init_auth()`.
"""

import os
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

oauth = OAuth()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allowed_emails() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def current_user() -> dict | None:
    return session.get("user")


def login_required(view):
    """Decorator: redirect anonymous users to /auth/login."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("auth_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

# Routes that don't require auth.
_PUBLIC_PATHS = {
    "/auth/login",
    "/auth/callback",
    "/auth/logout",
    "/auth/denied",
    "/api/health",
}


def init_auth(app: Flask) -> None:
    """Wire OAuth + a before_request guard onto the Flask app."""
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY env var is required (used for Flask session cookies)."
        )
    app.secret_key = secret_key

    # Cookie hardening. SESSION_COOKIE_SECURE=True only works over HTTPS.
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_DEBUG", "0") != "1",
    )

    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    @app.before_request
    def _require_login():
        # Allow public paths and static files to bypass.
        if request.path in _PUBLIC_PATHS:
            return None
        if request.path.startswith("/static/"):
            return None
        if current_user():
            return None
        # Send everything else through Google login.
        return redirect(url_for("auth_login", next=request.path))

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/auth/login")
    def auth_login():
        next_url = request.args.get("next") or "/"
        session["post_login_redirect"] = next_url
        redirect_uri = url_for("auth_callback", _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    @app.route("/auth/callback")
    def auth_callback():
        token = oauth.google.authorize_access_token()
        userinfo = token.get("userinfo") or {}
        email = (userinfo.get("email") or "").lower()
        verified = userinfo.get("email_verified", False)

        if not email or not verified:
            return redirect(url_for("auth_denied", reason="unverified"))

        if email not in _allowed_emails():
            return redirect(url_for("auth_denied", reason="not_allowlisted", email=email))

        session["user"] = {
            "email": email,
            "name": userinfo.get("name", email),
            "picture": userinfo.get("picture"),
        }
        next_url = session.pop("post_login_redirect", "/")
        return redirect(next_url)

    @app.route("/auth/logout")
    def auth_logout():
        session.clear()
        return redirect(url_for("auth_login"))

    @app.route("/auth/denied")
    def auth_denied():
        reason = request.args.get("reason", "")
        email = request.args.get("email", "")
        message = {
            "unverified": "האימייל שלך לא מאומת אצל Google.",
            "not_allowlisted": f"האימייל {email} לא מורשה לגשת למערכת. פנה למנהל המערכת.",
        }.get(reason, "שגיאה באימות.")
        # Minimal RTL Hebrew page — keeps the auth flow self-contained.
        return render_template_string(
            """
            <!doctype html>
            <html lang="he" dir="rtl">
            <head><meta charset="utf-8"><title>גישה נדחתה</title>
            <style>
              body { font-family: system-ui, sans-serif; max-width: 480px;
                     margin: 80px auto; padding: 24px; text-align: center; }
              .card { background: #fef3f2; border: 1px solid #fecdca;
                      border-radius: 12px; padding: 24px; }
              a { color: #2563eb; }
            </style></head>
            <body>
              <div class="card">
                <h1>🚫 גישה נדחתה</h1>
                <p>{{ message }}</p>
                <p><a href="{{ url_for('auth_login') }}">נסה שוב עם חשבון אחר</a></p>
              </div>
            </body>
            </html>
            """,
            message=message,
        ), 403
