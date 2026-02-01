"""WSGI entry point for production deployment"""
# IMPORTANT: Must monkey-patch BEFORE importing Flask
import gevent.monkey
gevent.monkey.patch_all()

import os
import datetime
from dotenv import load_dotenv

load_dotenv('.env.production')

from app import app, socketio, logger

if __name__ == "__main__":
    logger.info("Starting QuizFabric production server on port 5710...")
    socketio.run(app, debug=False, host="0.0.0.0", port=5710)
else:
    # For gunicorn WSGI deployment
    logger.info("QuizFabric WSGI application loaded for gunicorn deployment")
