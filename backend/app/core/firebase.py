"""Firebase from the server side (firebase-admin): one Firebase app for the whole API process.

FIREBASE_SERVICE_ACCOUNT is the service-account JSON (Firebase console > Project settings > Service
accounts > Generate new private key), pasted as ONE line. It is a secret: only in `.env` and on Render.
Empty = Firebase is off (local development without Firebase, and tests).
"""
import json
import threading

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings

_lock = threading.Lock()  # two first requests at the same moment must not both create the app


def enabled() -> bool:
    return bool(settings.FIREBASE_SERVICE_ACCOUNT)


def app() -> firebase_admin.App:
    with _lock:
        try:
            return firebase_admin.get_app()
        except ValueError:  # not created yet
            info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT)
            return firebase_admin.initialize_app(credentials.Certificate(info))


def firestore_client():
    from firebase_admin import firestore  # imported here: loads Google's Firestore library only when used
    return firestore.client(app())
