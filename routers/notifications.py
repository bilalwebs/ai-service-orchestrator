from fastapi import APIRouter, HTTPException
from schemas.models import FCMTokenRegister, NotificationPayload
from schemas.response import api_response
from tools.database_service import db_service
from tools.notification_service import notify_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/register")
async def register_fcm_token(body: FCMTokenRegister):
    """
    Register a user's device FCM token. 
    Called by the mobile app after login and FCM initialization.
    """
    db_service.register_fcm_token(
        user_id=body.user_id,
        fcm_token=body.fcm_token,
        device_id=body.device_id
    )
    return api_response(
        success=True, 
        message="FCM token registered successfully"
    )

@router.post("/test/{user_id}")
async def test_notification(user_id: str, payload: NotificationPayload):
    """
    Test endpoint to trigger a push notification to a specific user.
    Mainly for development and debugging.
    """
    # Check if user has tokens first
    tokens = db_service.get_fcm_tokens(user_id)
    if not tokens:
        raise HTTPException(
            status_code=404, 
            detail=f"No registered FCM tokens found for user {user_id}"
        )
        
    success_count = notify_user(
        user_id=user_id,
        title=payload.title,
        body=payload.body,
        data=payload.data
    )
    
    if success_count == 0:
        raise HTTPException(
            status_code=500, 
            detail="Failed to deliver notification to any devices."
        )
        
    return api_response(
        success=True, 
        message=f"Test notification sent to {success_count} device(s)."
    )
