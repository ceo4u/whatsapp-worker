import sys
import os
import threading
import asyncio

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

from dotenv import load_dotenv
load_dotenv(os.path.join(app_dir, '.env'))

from main import app

# Fork-safe WSGI runner for LiteSpeed / Passenger
_lock = threading.Lock()
_middleware = None
_thread = None

def get_middleware():
    global _middleware, _thread
    if _middleware is None or _thread is None or not _thread.is_alive():
        with _lock:
            if _middleware is None or _thread is None or not _thread.is_alive():
                loop = asyncio.new_event_loop()
                _thread = threading.Thread(target=loop.run_forever, daemon=True)
                _thread.start()
                from a2wsgi import ASGIMiddleware
                _middleware = ASGIMiddleware(app, loop=loop)
    return _middleware

def application(environ, start_response):
    # Pure WSGI instant health-check route (bypass ASGI/a2wsgi)
    path = environ.get('PATH_INFO', '').rstrip('/')
    if path == '/ping':
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [b'{"status":"ok","mode":"pure_wsgi"}']

    try:
        mw = get_middleware()
        # list() forces immediate consumption of the generator for LiteSpeed
        return list(mw(environ, start_response))
    except Exception:
        import traceback
        err_msg = traceback.format_exc()
        try:
            with open(os.path.join(app_dir, "startup_error.log"), "w") as f:
                f.write(err_msg)
        except Exception:
            pass
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain; charset=utf-8')])
        return [f"WSGI Runtime Error:\n\n{err_msg}".encode("utf-8")]
