"""Runs the API on an in-memory database, with demo accounts. For local frontend work only.

Everything resets when the process stops, and this is NOT a real MongoDB: it cannot prove the
unique-index and concurrency guarantees. Use MONGODB_URI against a real database for those.

    .venv\\Scripts\\python dev_server.py
"""

import uvicorn
from mongomock_motor import AsyncMongoMockClient

from app.config import Settings
from app.main import create_app

settings = Settings(app_env="dev", demo_mode_enabled=True, outbox_enabled=True)
app = create_app(settings, db=AsyncMongoMockClient()["unio_dev"])

if __name__ == "__main__":
    print("UNIO dev server on http://localhost:8000  (in-memory data, resets on restart)")
    print("Docs: http://localhost:8000/docs   Demo password: " + settings.demo_user_password)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
