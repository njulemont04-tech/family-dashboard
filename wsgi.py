# --- START: PRODUCTION WEBSOCKET CONFIGURATION ---
# This MUST be the first thing to run, before any other imports,
# to ensure that the standard library is patched for green concurrency.
import eventlet

eventlet.monkey_patch()
# --- END: PRODUCTION WEBSOCKET CONFIGURATION ---

import os
from app import app, socketio

# Get the port from the environment, default to 10000 for Render
port = int(os.environ.get("PORT", 10000))

# This is the official, high-level way to start a Flask-SocketIO server.
socketio.run(app, host="0.0.0.0", port=port)
