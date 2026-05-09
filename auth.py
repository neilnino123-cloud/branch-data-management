import streamlit as st
import itsdangerous
from datetime import datetime
from config import USERS

# ✅ Get secret from Streamlit secrets (cloud-safe)
SECRET_KEY = st.secrets["general"]["SECRET_KEY"]
SESSION_TIMEOUT_DAYS = 30
signer = itsdangerous.TimestampSigner(SECRET_KEY)


def create_session_token(username: str, role: str, branch: str = None, team: str = None) -> str:
    """Create a signed session token"""
    payload = f"{username}|{role}|{branch or 'None'}|{team or 'None'}|{datetime.now().timestamp()}"
    return signer.sign(payload).decode()


def validate_token(token: str) -> dict | None:
    """Validate and decode session token"""
    try:
        payload = signer.unsign(
            token, max_age=SESSION_TIMEOUT_DAYS * 86400).decode()
        parts = payload.split("|")
        return {
            "username": parts[0],
            "role": parts[1],
            "branch": parts[2] if parts[2] != "None" else None,
            "team": parts[3] if len(parts) > 3 and parts[3] != "None" else None
        }
    except Exception:
        return None


def login(username: str, password: str) -> dict | None:
    """Authenticate user and create session"""
    user = USERS.get(username)

    if user and user["password"] == password:  # ⚠️ Use bcrypt in production!
        token = create_session_token(
            username, user["role"], user.get("branch"), user.get("team")
        )

        # Store in session state (Streamlit Cloud compatible)
        st.session_state.user = {
            "username": username,
            "role": user["role"],
            "branch": user.get("branch"),
            "team": user.get("team")
        }
        st.session_state.auth_token = token
        st.session_state._auth_state = "authenticated"

        return st.session_state.user
    return None


def logout():
    """Clear user session"""
    st.session_state.pop("user", None)
    st.session_state.pop("auth_token", None)
    st.session_state._auth_state = "idle"
    st.rerun()


def get_current_user() -> dict | None:
    """Get authenticated user from session"""
    # Priority 1: Active authenticated session
    if st.session_state.get("_auth_state") == "authenticated" and "user" in st.session_state:
        # Validate token hasn't expired
        token = st.session_state.get("auth_token")
        if token and validate_token(token):
            return st.session_state.user

    # Priority 2: Try to restore from stored token (page refresh scenario)
    # Note: Streamlit Cloud doesn't persist session_state perfectly across reruns
    # For production, consider a proper backend auth system
    return None
