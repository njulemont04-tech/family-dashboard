import os
import eventlet
from app import app, socketio

# This code is safe to run on import
port = int(os.environ.get("PORT", 10000))

if __name__ == "__main__":
    # This block ONLY runs when we execute `python wsgi.py` directly.
    # It will NOT run when `flask db` imports this file.

    # --- START: PRODUCTION WEBSOCKET CONFIGURATION ---
    eventlet.monkey_patch()
    # --- END: PRODUCTION WEBSOCKET CONFIGURATION ---

    # Start the official server
    socketio.run(app, host="0.0.0.0", port=port)
