import eventlet
import eventlet.wsgi
import os
from app import app

# Get the port from the environment, default to 10000 for Render
port = int(os.environ.get("PORT", 10000))

# This is the most direct and stable way to run an Eventlet WSGI server.
# It completely bypasses Gunicorn and any "smart" runners.
# We are telling eventlet to listen on all interfaces at the specified port,
# and to serve our main Flask 'app' object.
eventlet.wsgi.server(eventlet.listen(("", port)), app)
