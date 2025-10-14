import eventlet
import eventlet.wsgi
import os
from app import app, socketio  # <-- We now import socketio as well

# Get the port from the environment, default to 10000 for Render
port = int(os.environ.get("PORT", 10000))

# We are telling eventlet to serve the 'socketio' super-app,
# which knows how to handle both HTTP and WebSockets.
eventlet.wsgi.server(
    eventlet.listen(("", port)), socketio
)  # <-- The critical change is here
