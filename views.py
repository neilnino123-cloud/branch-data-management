import streamlit as st
import pandas as pd
from datetime import datetime
from database import append_to_sheet, get_sheet_data, get_all_sheets_data, normalize_df_columns
from config import BRANCH_SHEETS, LEYTE_CUSTOMERS, SAMAR_CUSTOMERS, CALBAYOG_CUSTOMERS, SOLEY_CUSTOMERS, PRODUCT_LIST, LEYTE_ENCODERS, SAMAR_ENCODERS, CALBAYOG_ENCODERS, SOLEY_ENCODERS, USERS
import plotly.express as px


def render_login_form():
    col1, col2, col3 = st.columns([4, 3, 4])
    with col2:
        with st.container(border=True, key="login_form"):
            st.write("\n")
            with st.container(horizontal=True, horizontal_alignment="center"):
                # ✅ Relative path for cloud compatibility
                st.image(
                    "logo4.png" if st.file_uploader else "logo3.png", width=250)
            with st.container():
                # st.subheader("Bibit Gamot Program", text_alignment="center")
                st.subheader("Please login to access your account",
                          text_alignment="center")
                with st.form("login_form", border=False):
                    username = st.text_input(
                        "Username", placeholder="Enter username")
                    password = st.text_input(
                        "Password", type="password", placeholder="Enter password")
                    st.write("\n")
                    submit = st.form_submit_button("Login", width="stretch")

                    if submit:
                        from auth import login
                        if username and password:
                            user = login(username, password)
                            if user:
                                st.success("✅ Login successful!")
                                st.rerun()
                            else:
                                st.error("❌ Invalid credentials.")
                        else:
                            st.warning(
                                "⚠️ Please enter both username and password.")

    st.markdown("""
    <style>
    .st-key-login_form { background-color: #f8f9fa; border-radius: 10px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)


def render_admin_view(user):
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.header("👑 Admin Dashboard")
        if st.button("🔄 Refresh Data", type="secondary"):
            get_sheet_data.clear()
            get_all_sheets_data.clear()
            st.rerun()

    branches = ["All Branches"] + list(BRANCH_SHEETS.keys())
    selected_branch = st.selectbox("Select Branch to View", branches)
    st.write("\n")

    if selected_branch == "All Branches":
        df = get_all_sheets_data()
    else:
        df = get_sheet_data(selected_branch)

    # ✅ Normalize columns for consistency
    df = normalize_df_columns(df)

    if not df.empty:
        st.dataframe(df, use_container_width=True)

        # ✅ TREND CHART SECTION
        st.divider()
        st.subheader("📈 Sales Trend by Product")

        all_products = ["All Products"] + \
            sorted(df["product"].dropna().unique().tolist())
        selected_chart_product = st.selectbox(
            "Filter by Product (Optional)", all_products, key="admin_chart_product")

        chart_df = prepare_trend_data(df, branch_filter=selected_branch)

        if not chart_df.empty:
            if selected_chart_product != "All Products":
                chart_df = chart_df[chart_df["product"]
                                    == selected_chart_product]

            if not chart_df.empty:
                fig = px.line(
                    chart_df,
                    x="date",
                    y="quantity",
                    color="product" if selected_chart_product == "All Products" else None,
                    markers=True,
                    title=f"Sales Trend - {selected_branch}" if selected_branch != "All Branches" else "Sales Trend - All Branches",
                    labels={"quantity": "Total Quantity", "date": "Date",
                            "product": "Product", "branch": "Branch"},
                    height=400
                )
                fig.update_layout(
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom",
                                y=1.02, xanchor="right", x=1),
                    xaxis_title="Date",
                    yaxis_title="Total Quantity"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ℹ️ No data for selected product filter.")
        else:
            st.info("ℹ️ No trend data available.")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Submissions", len(df))
    with col2:
        if "timestamp" in df.columns and not df["timestamp"].isna().all():
            latest = pd.to_datetime(df["timestamp"]).max()
            st.metric("Latest Submission", latest.strftime("%m/%d %H:%M"))
        else:
            st.metric("Latest Submission", "N/A")


def render_moderator_view(user):
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.header(f"👨‍💼 Moderator Dashboard: {user['branch']}")
        if st.button("🔄 Refresh Data", type="secondary"):
            get_sheet_data.clear()
            get_all_sheets_data.clear()
            st.rerun()

    st.divider()
    st.subheader("📝 All Transactions")
    st.caption("Complete transaction history")

    df = get_sheet_data(user["branch"])
    df = normalize_df_columns(df)
    df_display = df.drop(columns=["username"], errors="ignore")


    if not df.empty:
        st.dataframe(df_display, use_container_width=True)

        # ✅ TREND CHART SECTION
        st.divider()
        st.subheader(f"📈 {user['branch']} Sales Trend by Product")

        all_products = ["All Products"] + \
            sorted(df["product"].dropna().unique().tolist())
        selected_chart_product = st.selectbox(
            "Filter by Product (Optional)", all_products, key=f"mod_chart_product_{user['branch']}")

        chart_df = prepare_trend_data(df, branch_filter=user["branch"])

        if not chart_df.empty:
            if selected_chart_product != "All Products":
                chart_df = chart_df[chart_df["product"]
                                    == selected_chart_product]

            if not chart_df.empty:
                fig = px.line(
                    chart_df,
                    x="date",
                    y="quantity",
                    color="product",
                    markers=True,
                    title=f"{user['branch']} - Sales Trend",
                    labels={"quantity": "Total Quantity",
                            "date": "Date", "product": "Product"},
                    height=400
                )
                fig.update_layout(
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom",
                                y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ℹ️ No data for selected product filter.")
        else:
            st.info("ℹ️ No trend data available.")
    else:
        st.info("ℹ️ No records yet.")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Submissions", len(df))
    with col2:
        if "timestamp" in df.columns and not df["timestamp"].isna().all():
            latest = pd.to_datetime(df["timestamp"]).max()
            st.metric("Latest Submission", latest.strftime("%m/%d %H:%M"))
        else:
            st.metric("Latest Submission", "N/A")

def get_encoder_list(branch: str, team: str = None) -> list[str]:
    """
    🌍 Branch-agnostic encoder list generator.
    Automatically handles dict-of-sets (LEYTE) and flat-lists (SAMAR, CALBAYOG, etc.)
    """
    # 🗂️ Centralized mapping: add new branches here only
    BRANCH_ENCODER_MAP = {
        "TWMC LEYTE": LEYTE_ENCODERS,
        "TWMC SAMAR": SAMAR_ENCODERS,
        "TWMC CALBAYOG": CALBAYOG_ENCODERS,
        "TWMC SOUTHERN LEYTE": SOLEY_ENCODERS,
    }
    
    source = BRANCH_ENCODER_MAP.get(branch)
    if not source:
        return ["-- Full Name --"]
        
    names = set()
    
    # 🔹 If dict-of-sets (e.g., LEYTE)
    if isinstance(source, dict):
        if team:
            # Match display team name to internal key via USERS
            team_key = next((k for k, v in USERS.items() 
                             if v.get("branch") == branch and v.get("team") == team), None)
            if team_key and team_key in source:
                val = source[team_key]
                names.update(val if isinstance(val, (set, list)) else {val})
        else:
            # Fallback: flatten all teams
            for val in source.values():
                names.update(val if isinstance(val, (set, list)) else {val})
                
    # 🔹 If flat list (e.g., SAMAR, CALBAYOG, SOLEY)
    elif isinstance(source, list):
        names.update(n for n in source if n and not n.startswith("--"))
        
    # ✅ Return sorted with consistent placeholder
    return ["-- Full Name --"] + sorted(names) if names else ["-- Full Name --"]


def render_encoder_view(user):
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.header(f"⌨️ Sales Portal: {user.get('team', 'General')}")
        if st.button("🔄 Refresh Data", type="secondary"):
            get_sheet_data.clear()
            get_all_sheets_data.clear()
            st.rerun()

    # Branch selection logic
    if user["branch"]:
        selected_branch = user["branch"]
        st.info(f"🔒 Assigned to: {selected_branch}")
    else:
        selected_branch = st.selectbox(
            "Select Target Branch", list(BRANCH_SHEETS.keys()))

    # ✅ Reset form logic
    if st.session_state.get("reset_encoder_form", False):
        for key in ["enc_name", "store_name", "product", "uom", "qty", "notes"]:
            st.session_state[key] = None if key == "qty" else "-- Select Customer --" if key == "store_name" else "-- Select Product --" if key == "product" else "-- Select Unit --" if key == "uom" else ""
        st.session_state.reset_encoder_form = False

    with st.expander("📝 Add Data Here"):
        # ✅ Initialize session state defaults
        defaults = {
            "enc_name": "", "store_name": "-- Select Customer --",
            "product": "-- Select Product --", "uom": "-- Select Unit --",
            "qty": 0, "notes": ""
        }
        for key, default in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default

        st.markdown("""
        <style>
        .stTextInput input { text-transform: uppercase; }
        </style>""", unsafe_allow_html=True)

        # ✅ Global dynamic encoder list (works for ANY branch)
        emp_list = get_encoder_list(user["branch"], user.get("team"))
        st.selectbox("Enter Full Name*", emp_list, key="enc_name")

        # Customer dropdown based on branch
        customer_list = {
            "TWMC LEYTE": LEYTE_CUSTOMERS,
            "TWMC SAMAR": SAMAR_CUSTOMERS,
            "TWMC CALBAYOG": CALBAYOG_CUSTOMERS,
            "TWMC SOUTHERN LEYTE": SOLEY_CUSTOMERS
        }.get(selected_branch, ["-- Select Customer --"])

        st.selectbox("Enter Store Name*", customer_list, key="store_name")

        # Product selection
        product_options = ["-- Select Product --"] + list(PRODUCT_LIST.keys())
        st.selectbox("Product", product_options, key="product")

        # Dynamic UOM based on product
        selected_product = st.session_state.product
        if selected_product in ("-- Select Product --", "-- OTHERS --") or not PRODUCT_LIST.get(selected_product):
            uom_options = ["-- Select Unit --"]
        else:
            uom_options = ["-- Select Unit --"] + \
                sorted(PRODUCT_LIST[selected_product])
        st.selectbox("UOM", uom_options, key="uom")

        st.number_input("Quantity", min_value=0, step=1, key="qty")
        st.text_area("Notes", key="notes")

        # Submit button
        if st.button("Submit Data"):
            # Validation
            errors = []
            if st.session_state.enc_name == "-- Full Name --":
                errors.append("Please enter your full name")
            if st.session_state.store_name == "-- Select Customer --":
                errors.append("Please select a customer")
            if st.session_state.product == "-- Select Product --":
                errors.append("Please select a product")
            if st.session_state.uom == "-- Select Unit --":
                errors.append("Please select a unit of measure")
            if st.session_state.qty <= 0:
                errors.append("Please enter a valid quantity")

            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                data = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "username": user["username"],
                    "role_team": f"Encoder - {user.get('team', 'General')}",
                    "enc_name": st.session_state.enc_name.strip().upper(),
                    "store_name": st.session_state.store_name,
                    "product": st.session_state.product,
                    "quantity": int(st.session_state.qty),
                    "uom": st.session_state.uom,
                    "notes": st.session_state.notes
                }

                with st.spinner("💾 Saving to Google Sheets..."):
                    success = append_to_sheet(selected_branch, data)

                if success:
                    st.success("✅ Data successfully saved!")
                    st.session_state.reset_encoder_form = True
                    st.rerun()
                else:
                    st.error("❌ Failed to save data. Please try again.")

    st.write("\n")
    st.subheader("Sales Transactions")

    df = get_sheet_data(selected_branch) if user["branch"] else pd.DataFrame()
    df = normalize_df_columns(df)
    df_display = df.drop(columns=["username"], errors="ignore")

    if not df.empty:
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("ℹ️ No data found for this selection.")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Submissions", len(df))
    with col2:
        if "timestamp" in df.columns and not df["timestamp"].isna().all():
            latest = pd.to_datetime(df["timestamp"]).max()
            st.metric("Latest Submission", latest.strftime("%m/%d %H:%M"))
        else:
            st.metric("Latest Submission", "N/A")


def prepare_trend_data(df: pd.DataFrame, branch_filter: str = None) -> pd.DataFrame:
    """Prepares dataframe for trend line chart with normalized columns."""
    if df.empty:
        return pd.DataFrame()

    # ✅ Ensure lowercase columns
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

    # Verify required columns
    required = ["timestamp", "product", "quantity"]
    if not all(col in df.columns for col in required):
        return pd.DataFrame()

    # Filter by branch if specified
    if branch_filter and branch_filter != "All Branches":
        if "source_branch" in df.columns:
            df = df[df["source_branch"] == branch_filter]

    # Convert timestamp to date
    df["date"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.date
    df = df.dropna(subset=["date", "product", "quantity"])

    # Aggregate by date + product (+ branch if showing all)
    group_cols = ["date", "product"]
    if "source_branch" in df.columns and branch_filter == "All Branches":
        group_cols.append("source_branch")

    grouped = df.groupby(group_cols)["quantity"].sum().reset_index()
    return grouped
