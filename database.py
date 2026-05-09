import gspread
import pandas as pd
import time
import streamlit as st
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_ID, BRANCH_SHEETS


@st.cache_resource(ttl=300)
def get_gsheet_client():
    """Initialize Google Sheets client with robust credential handling"""
    sa = dict(st.secrets["gcp_service_account"])

    # 🔑 FIX: Handle newline escaping issues that break JWT signatures
    if "private_key" in sa:
        # Replace literal \n strings with actual newlines, and remove extra whitespace
        sa["private_key"] = sa["private_key"].replace('\\n', '\n').strip()

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file"
    ]

    return gspread.authorize(Credentials.from_service_account_info(sa, scopes=scopes))


def _safe_api_call(func, max_retries=3, base_delay=2):
    """Retry wrapper for Google API calls with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except gspread.exceptions.APIError as e:
            error_str = str(e).upper()
            if "503" in error_str or "UNAVAILABLE" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < max_retries - 1:
                    wait = base_delay * (2 ** attempt)
                    st.warning(
                        f"⏳ Google API busy. Retrying in {wait}s... ({attempt+1}/{max_retries})")
                    time.sleep(wait)
                    continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(base_delay)
                continue
            raise


@st.cache_data(ttl=60, show_spinner="Loading branch data...")
def get_sheet_data(branch: str) -> pd.DataFrame:
    """Fetch data for a single branch sheet"""
    client = get_gsheet_client()
    sheet_name = BRANCH_SHEETS.get(branch)

    if not sheet_name:
        return pd.DataFrame()

    def _fetch():
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name)
        records = worksheet.get_all_records()
        return pd.DataFrame(records) if records else pd.DataFrame()

    try:
        return _safe_api_call(_fetch)
    except Exception as e:
        st.error(f"❌ Failed to load {branch}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner="Loading all branches...")
def get_all_sheets_data() -> pd.DataFrame:
    """Fetch and merge data from all branch sheets"""
    client = get_gsheet_client()
    all_frames = []

    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    for branch, sheet_name in BRANCH_SHEETS.items():
        def _fetch_branch():
            worksheet = spreadsheet.worksheet(sheet_name)
            records = worksheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                df.insert(0, "Source_Branch", branch)
                return df
            return None

        try:
            df = _safe_api_call(_fetch_branch)
            if df is not None and not df.empty:
                all_frames.append(df)
        except Exception as e:
            st.warning(f"⚠️ Skipping {branch}: {e}")
            continue

    return pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()


def append_to_sheet(branch: str, data: dict) -> bool:
    """Append a row to the specified branch sheet with error handling"""
    client = get_gsheet_client()
    sheet_name = BRANCH_SHEETS.get(branch)

    if not sheet_name:
        st.error(f"❌ Invalid branch: {branch}")
        return False

    try:
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name)

        # Order must match your Google Sheet columns
        row = [
            data.get("timestamp"),
            data.get("username"),
            data.get("role_team"),
            data.get("enc_name"),
            data.get("store_name"),
            data.get("product"),
            data.get("quantity"),
            data.get("uom"),
            data.get("notes")
        ]

        def _append():
            worksheet.append_row(row, value_input_option="USER_ENTERED")

        _safe_api_call(_append)
        return True

    except Exception as e:
        st.error(f"❌ Failed to save data: {str(e)}")
        return False


def normalize_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to lowercase with underscores for consistency"""
    if df.empty:
        return df
    return df.rename(columns=lambda x: x.strip().lower().replace(" ", "_"))
