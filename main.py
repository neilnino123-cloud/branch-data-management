import streamlit as st
import os
from auth import get_current_user, logout
from views import render_login_form, render_admin_view, render_moderator_view, render_encoder_view, render_market_survey_view

# ✅ Cross-platform logo handling
LOGO_PATH = "logo3.png" if os.path.exists("logo3.png") else None

st.set_page_config(
    page_title="Branch Data Manager",
    layout="wide",
    page_icon=LOGO_PATH
)


def main():
    user = get_current_user()

    if not user:
        render_login_form()
        return

    # Sidebar with logout
    with st.sidebar:
        if os.path.exists("./logo3.png"):
            st.logo("./logo3.png", size="large")

        st.success(f"Logged in as - {user['role'].capitalize()}")

        if st.button("🚪 Logout"):
            logout()
            st.rerun()


    # Route based on role
    if user["role"] == "admin":
        render_admin_view(user)
    elif user["role"] == "moderator":
        render_moderator_view(user)
    elif user["role"] == "encoder":
        render_encoder_view(user)
    elif user["role"] == "dsp":
        render_market_survey_view(user)
    else:
        st.error("❌ Unauthorized role. Please contact administrator.")


if __name__ == "__main__":
    main()

