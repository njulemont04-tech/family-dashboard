import os
from app import app, socketio

# Get the port from the environment, default to 10000 for Render
port = int(os.environ.get("PORT", 10000))

# This is the official, high-level way to start a Flask-SocketIO server.
# It will automatically and correctly use the Eventlet server because it's installed.
# We run it directly with Python, avoiding Gunicorn entirely.
socketio.run(app, host="0.0.0.0", port=port)
