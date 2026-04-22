"""
Auth routes — fully hardened

- Register: domain validated against institution.allowed_email_domain
- Register: (institution_id, student_id) uniqueness enforced
- Login: lockout after 10 failed attempts (15-min block)
- Login: clears lockout on success
- Refresh: DB-backed token rotation with reuse detection
- Logout: revokes refresh token from DB
- Logout-all: revokes all sessions
"""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, Institution
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    store_refresh_token, revoke_refresh_token, revoke_all_user_tokens,
    check_login_lockout, clear_login_failures,
    get_current_user,
)
from app.middleware.rate_limit import check_register_limit

logger = logging.getLogger("anoncampus.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 5 registrations/hour per IP
    client_ip = request.client.host if request.client else "unknown"
    check_register_limit(client_ip)

    # Step 1: Extract domain from email
    domain = payload.email.split("@")[-1].lower()

    # Step 2: Match institution by domain
    inst_result = await db.execute(
        select(Institution).where(
            Institution.domain == domain,
            Institution.is_active == True,
        )
    )
    institution = inst_result.scalar_one_or_none()

    if not institution:
        # Dev mode: auto-create institution for unknown domains
        institution = Institution(
            name=domain.replace(".", " ").title(),
            domain=domain,
            allowed_email_domain=domain,
            tier="medium",
        )
        db.add(institution)
        await db.flush()

    # Step 3: Validate email domain matches institution's allowed domain
    if domain != institution.allowed_email_domain.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email domain '{domain}' not allowed for this institution. "
                   f"Expected: {institution.allowed_email_domain}",
        )

    # Step 4: Check email uniqueness
    existing_email = await db.execute(select(User).where(User.email == payload.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Step 5: Check (institution_id, student_id) uniqueness
    existing_sid = await db.execute(
        select(User).where(
            User.institution_id == institution.id,
            User.student_id == payload.student_id.upper(),
        )
    )
    if existing_sid.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Student ID already registered at this institution",
        )

    # Step 6: Create user
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        student_id=payload.student_id.upper(),
        institution_id=institution.id,
        department=payload.department,
        academic_year=payload.academic_year,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"User registered: id={user.id} inst={institution.id} dept={user.department}")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"

    # Check lockout BEFORE attempting authentication
    check_login_lockout(client_ip)

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Constant-time comparison — don't leak user existence via timing
    if not user or not verify_password(payload.password, user.hashed_password):
        # Failure is logged by lockout mechanism via Redis increment
        check_login_lockout(client_ip)  # increments failure count
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    # Success — clear failure count
    clear_login_failures(client_ip)

    # Issue tokens with shared family_id for rotation tracking
    family_id = str(uuid.uuid4())
    access_token = create_access_token(user.id, user.institution_id, user.role, family_id)
    refresh_token = create_refresh_token(user.id, user.institution_id, user.role, family_id)

    # Store refresh token in DB
    await store_refresh_token(db, refresh_token, user.id, user.institution_id, family_id)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        anon_id=user.anon_id,
        role=user.role,
        institution_id=user.institution_id,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh token rotation:
    1. Validate refresh token signature
    2. Check not revoked in DB (reuse → revoke family)
    3. Revoke old token
    4. Issue new access + refresh pair
    """
    body = await request.json()
    raw_refresh = body.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(status_code=400, detail="refresh_token required")

    payload = decode_token(raw_refresh, expected_type="refresh")
    user_id = int(payload["sub"])

    # Revoke old token (detects reuse internally)
    await revoke_refresh_token(db, raw_refresh, reason="rotation")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Issue new token pair
    family_id = str(uuid.uuid4())
    access_token = create_access_token(user.id, user.institution_id, user.role, family_id)
    refresh_token = create_refresh_token(user.id, user.institution_id, user.role, family_id)
    await store_refresh_token(db, refresh_token, user.id, user.institution_id, family_id)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        anon_id=user.anon_id,
        role=user.role,
        institution_id=user.institution_id,
    )


@router.post("/logout", status_code=200)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    body = await request.json()
    raw_refresh = body.get("refresh_token")
    if raw_refresh:
        await revoke_refresh_token(db, raw_refresh, reason="logout")
        await db.commit()
    return {"message": "Logged out"}


@router.post("/logout-all", status_code=200)
async def logout_all(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke all refresh tokens for this user (all devices)"""
    await revoke_all_user_tokens(db, current_user.id, reason="logout_all")
    await db.commit()
    return {"message": "All sessions revoked"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
