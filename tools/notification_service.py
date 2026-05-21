import os
import logging
from typing import Optional, Dict, Any, List
import firebase_admin
from firebase_admin import credentials, messaging
from tools.database_service import db_service

logger = logging.getLogger(__name__)

# Track if firebase is initialized to avoid dual-initialization errors
_firebase_initialized = False

def init_firebase():
    """Initialise Firebase Admin SDK using credentials from env."""
    global _firebase_initialized
    if _firebase_initialized:
        return
        
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-service-account.json")
    
    if not os.path.exists(cred_path):
        logger.warning(f"[FCM] Credentials file not found at {cred_path}. Push notifications will be disabled.")
        return
        
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("[FCM] Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error(f"[FCM] Failed to initialize Firebase: {e}")

def send_push_notification(fcm_token: str, title: str, body: str, data: Optional[Dict[str, str]] = None) -> bool:
    """Send a single push notification to a specific FCM token."""
    if not _firebase_initialized:
        logger.warning("[FCM] Cannot send notification - Firebase not initialized.")
        return False
        
    # FCM data payload requires all values to be strings
    str_data = {}
    if data:
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                import json
                str_data[k] = json.dumps(v)
            else:
                str_data[k] = str(v)
                
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=str_data,
            token=fcm_token,
        )
        
        response = messaging.send(message)
        logger.info(f"[FCM] Successfully sent message: {response}")
        return True
    except messaging.UnregisteredError:
        logger.info(f"[FCM] Token {fcm_token} is unregistered. Removing from database.")
        db_service.remove_fcm_token(fcm_token)
        return False
    except Exception as e:
        logger.error(f"[FCM] Error sending message to token {fcm_token}: {e}")
        return False

def notify_user(user_id: str, title: str, body: str, data: Optional[Dict[str, Any]] = None) -> int:
    """Look up all FCM tokens for a user and send notification to each device."""
    tokens = db_service.get_fcm_tokens(user_id)
    
    if not tokens:
        logger.info(f"[FCM] No registered tokens found for user {user_id}. Skipping notification.")
        return 0
        
    success_count = 0
    for token in tokens:
        if send_push_notification(token, title, body, data):
            success_count += 1
            
    logger.info(f"[FCM] Sent notifications to {success_count}/{len(tokens)} devices for user {user_id}")
    return success_count
