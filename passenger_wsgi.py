import sys
import os

# Set base directory
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# Add virtual environment site-packages if present (Hostinger / cPanel)
user_home = os.path.expanduser("~")
potential_venvs = [
    os.path.join(user_home, "virtualenv", "whatsapp-worker", "3.11", "lib", "python3.11", "site-packages"),
    os.path.join(user_home, "virtualenv", "whatsapp-worker", "3.10", "lib", "python3.10", "site-packages"),
    os.path.join(app_dir, "venv", "Lib", "site-packages"),
    os.path.join(app_dir, ".venv", "lib", "python3.11", "site-packages"),
]
for p in potential_venvs:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(app_dir, '.env'))

    from a2wsgi import ASGIMiddleware
    from main import app

    application = ASGIMiddleware(app)

except Exception:
    import traceback
    err_msg = traceback.format_exc()

    # Log to file for easy debugging
    try:
        with open(os.path.join(app_dir, "startup_error.log"), "w") as f:
            f.write(err_msg)
    except Exception:
        pass

    # Instant response instead of hanging / timeout
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain; charset=utf-8')])
        return [f"WSGI Startup Error:\n\n{err_msg}".encode("utf-8")]
