import os
from app import app, socketio

# The port number is provided by Render's environment variables.
# Default to 10000 if it's not set.
port = int(os.environ.get("PORT", 10000))

if __name__ == "__main__":
    # We use socketio.run() which is smart enough to use the eventlet server
    # when it's installed.
    socketio.run(app, host="0.0.0.0", port=port)
