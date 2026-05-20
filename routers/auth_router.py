from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from schemas.user_schema import UserRegister

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token
)

router = APIRouter()

# Temporary database
users_db = []

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# =========================
# REGISTER API
# =========================
@router.post("/register")
def register(user: UserRegister):

    for db_user in users_db:
        if db_user["email"] == user.email:
            raise HTTPException(
                status_code=400,
                detail="Email already exists"
            )

    hashed_pw = hash_password(user.password)

    new_user = {
        "name": user.name,
        "email": user.email,
        "password": hashed_pw
    }

    users_db.append(new_user)

    return {
        "message": "User registered successfully",
        "name": user.name,
        "email": user.email,
        "hashed_password": hashed_pw
    }


# =========================
# LOGIN API
# =========================
@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):

    for db_user in users_db:

        if db_user["email"] == form_data.username:

            if verify_password(form_data.password, db_user["password"]):

                token = create_access_token(
                    data={"sub": form_data.username}
                )

                return {
                    "message": "Login successful",
                    "email": db_user["email"],
                    "access_token": token,
                    "token_type": "bearer"
                }

    raise HTTPException(
        status_code=401,
        detail="Invalid credentials"
    )


# =========================
# PROTECTED PROFILE API
# =========================
@router.get("/profile")
def profile(token: str = Depends(oauth2_scheme)):

    user = verify_token(token)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    return {
        "message": f"Welcome {user}"
    }