import streamlit as st
import pandas as pd
from datetime import datetime
from database import append_to_sheet, get_sheet_data, get_all_sheets_data, normalize_df_columns
from config import BRANCH_SHEETS, LEYTE_CUSTOMERS, SAMAR_CUSTOMERS, CALBAYOG_CUSTOMERS, SOLEY_CUSTOMERS, PRODUCT_LIST, LEYTE_ENCODERS, SAMAR_ENCODERS, CALBAYOG_ENCODERS, SOLEY_ENCODERS, USERS
import plotly.express as px
from zoneinfo import ZoneInfo


# Define Philippine Time
PHT = ZoneInfo("Asia/Manila")

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

def prepare_bar_chart_data(df: pd.DataFrame, branch_filter: str = None, 
                           encoder_filter: str = None, product_filter: str = None,
                           date_range: tuple = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")
    
    # 🔍 Find encoder column dynamically
    enc_col = None
    for col in ["enc_name", "encoder", "encoder_name", "fullname"]:
        if col in df.columns:
            enc_col = col
            break
        
    
    required = ["timestamp", "product", "quantity"]
    if enc_col:
        required.append(enc_col)
        
    if not all(col in df.columns for col in required):
        # Return data even without encoder column
        if not all(col in df.columns for col in ["timestamp", "product", "quantity"]):
            return pd.DataFrame()
    
    # Filter by branch
    if branch_filter and branch_filter != "All Branches" and "source_branch" in df.columns:
        df = df[df["source_branch"] == branch_filter]
    
    # 🔧 Filter by encoder (use dynamic column name)
    if encoder_filter and encoder_filter != "All Encoders" and enc_col:
        df = df[df[enc_col] == encoder_filter]
    
    # Filter by product
    if product_filter and product_filter != "All Products":
        df = df[df["product"] == product_filter]
    
    # Filter by date range
    if date_range and date_range[0] and date_range[1]:
        df["date_only"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.date
        df = df[(df["date_only"] >= date_range[0]) & (df["date_only"] <= date_range[1])]
    
    # Aggregate - use dynamic encoder column
    group_cols = [enc_col, "product"] if enc_col else ["product"]
    if "source_branch" in df.columns and branch_filter == "All Branches":
        group_cols.append("source_branch")
    
    grouped = df.groupby(group_cols + ["date_only"])["quantity"].sum().reset_index()
    grouped = grouped.rename(columns={"date_only": "date", "quantity": "total_qty"})
    return grouped

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

        # =============================================================================
        # 📊 DYNAMIC BAR CHART (Progressive Filtering Fix)
        # =============================================================================
        st.divider()
        st.subheader("📊 Smahc Pull out Breakdown by Encoder & Product")

        # Start with full dataset
        df_prog = df.copy()

        col_f1, col_f2, col_f3, col_f4 = st.columns(4)

        with col_f1:
            branch_options = ["All Branches"] + list(BRANCH_SHEETS.keys())
            bar_branch = st.selectbox("Filter by Branch", branch_options, key="bar_branch")

        # 1️ Apply Branch Filter immediately
        if bar_branch != "All Branches" and "source_branch" in df_prog.columns:
            df_prog = df_prog[df_prog["source_branch"] == bar_branch]

        with col_f2:
            enc_col = next((c for c in ["enc_name", "encoder", "fullname", "full_name", "name"] if c in df_prog.columns), None)
            encoders = ["All Encoders"]
            if enc_col and not df_prog.empty:
                enc_list = df_prog[enc_col].dropna().astype(str).str.strip().unique().tolist()
                encoders += sorted([e for e in enc_list if e])
            bar_encoder = st.selectbox("Filter by Encoder", encoders, key="bar_encoder")

        # 2️⃣ Apply Encoder Filter immediately (now product dropdown only sees this encoder's data)
        if bar_encoder != "All Encoders" and enc_col:
            df_prog = df_prog[df_prog[enc_col] == bar_encoder]

        with col_f3:
            products = ["All Products"]
            if not df_prog.empty and "product" in df_prog.columns:
                prod_list = df_prog["product"].dropna().astype(str).str.strip().unique().tolist()
                products += sorted([p for p in prod_list if p])
            bar_product = st.selectbox("Filter by Product", products, key="bar_product")

        with col_f4:
            if not df_prog.empty and "timestamp" in df_prog.columns:
                dates = pd.to_datetime(df_prog["timestamp"], errors="coerce").dropna()
                min_d, max_d = (dates.min().date(), dates.max().date()) if not dates.empty else (None, None)
            else:
                min_d, max_d = None, None
            bar_date = st.date_input("Date Range", value=(min_d, max_d) if min_d else None,
                                    min_value=min_d, max_value=max_d, key="bar_date")

        # 3️⃣ Apply Product & Date Filters for Final Chart
        if bar_product != "All Products":
            df_prog = df_prog[df_prog["product"] == bar_product]

        if isinstance(bar_date, tuple) and len(bar_date) == 2:
            df_prog["temp_date"] = pd.to_datetime(df_prog["timestamp"], errors="coerce").dt.date
            df_prog = df_prog[(df_prog["temp_date"] >= bar_date[0]) & (df_prog["temp_date"] <= bar_date[1])]
            df_prog.drop(columns=["temp_date"], inplace=True)

        # ── Render Chart ──
        if not df_prog.empty:
            x_axis = "product" if bar_encoder != "All Encoders" and enc_col else (enc_col if enc_col else "product")
            color_axis = "product" if bar_encoder == "All Encoders" or not enc_col else None

            # Aggregate to prevent duplicate bars
            group_cols = [x_axis] + ([color_axis] if color_axis else [])
            chart_df = df_prog.groupby(group_cols)["quantity"].sum().reset_index().rename(columns={"quantity": "total_qty"})

            title = f"Sales Breakdown - {bar_encoder}" if bar_encoder != "All Encoders" else f"Sales Breakdown - {bar_branch}"
            
            fig = px.bar(chart_df, x=x_axis, y="total_qty", color=color_axis, barmode="group", 
                        title=title, height=400, labels={"total_qty": "Total Quantity", "product": "Product"})
            fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.02, x=1), bargap=0.15)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ℹ️ No data matches the selected filters.")

        # ✅ TREND CHART SECTION
        st.divider()
        st.subheader("📈 Smahc Pull out Trend by Product")

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
            st.metric("Latest Submission", latest.strftime("%m/%d %I:%M %p"))
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
    df = normalize_df_columns(df)  # ✅ Normalize columns
    df_display = df.drop(columns=["username"], errors="ignore")

    if not df.empty:
        st.dataframe(df_display, use_container_width=True)
        # =============================================================================
        # 📊 MODERATOR: DYNAMIC SALES BREAKDOWN (Branch-Locked)
        # =============================================================================
        st.divider()
        st.subheader(f"📊 {user['branch']} Smahc Pull out Breakdown")

        # df is already locked to user["branch"]
        df_prog = df.copy()
        col_f1, col_f2, col_f3 = st.columns(3)

        with col_f1:
            enc_col = next((c for c in ["enc_name", "encoder", "fullname", "full_name", "name"] if c in df_prog.columns), None)
            encoders = ["All Encoders"]
            if enc_col and not df_prog.empty:
                enc_list = df_prog[enc_col].dropna().astype(str).str.strip().unique().tolist()
                encoders += sorted([e for e in enc_list if e])
            bar_encoder = st.selectbox("Filter by Encoder", encoders, key=f"mod_bar_enc_{user['branch']}")

        # Apply encoder filter before populating products
        if bar_encoder != "All Encoders" and enc_col:
            df_prog = df_prog[df_prog[enc_col] == bar_encoder]

        with col_f2:
            products = ["All Products"]
            if not df_prog.empty and "product" in df_prog.columns:
                prod_list = df_prog["product"].dropna().astype(str).str.strip().unique().tolist()
                products += sorted([p for p in prod_list if p])
            bar_product = st.selectbox("Filter by Product", products, key=f"mod_bar_prod_{user['branch']}")

        with col_f3:
            if not df_prog.empty and "timestamp" in df_prog.columns:
                dates = pd.to_datetime(df_prog["timestamp"], errors="coerce").dropna()
                min_d, max_d = (dates.min().date(), dates.max().date()) if not dates.empty else (None, None)
            else:
                min_d, max_d = None, None
            bar_date = st.date_input("Date Range", value=(min_d, max_d) if min_d else None,
                                    min_value=min_d, max_value=max_d, key=f"mod_bar_date_{user['branch']}")

        # Apply product & date filters
        if bar_product != "All Products":
            df_prog = df_prog[df_prog["product"] == bar_product]
        if isinstance(bar_date, tuple) and len(bar_date) == 2:
            df_prog["temp_date"] = pd.to_datetime(df_prog["timestamp"], errors="coerce").dt.date
            df_prog = df_prog[(df_prog["temp_date"] >= bar_date[0]) & (df_prog["temp_date"] <= bar_date[1])]
            df_prog.drop(columns=["temp_date"], inplace=True)

        # Render
        if not df_prog.empty:
            x_axis = "product" if bar_encoder != "All Encoders" and enc_col else (enc_col if enc_col else "product")
            color_axis = "product" if bar_encoder == "All Encoders" or not enc_col else None
            group_cols = [x_axis] + ([color_axis] if color_axis else [])
            chart_df = df_prog.groupby(group_cols)["quantity"].sum().reset_index().rename(columns={"quantity": "total_qty"})
            
            title = f"Sales Breakdown - {bar_encoder}" if bar_encoder != "All Encoders" else f"Sales Breakdown - {user['branch']}"
            fig = px.bar(chart_df, x=x_axis, y="total_qty", color=color_axis, barmode="group", 
                        title=title, height=400, labels={"total_qty": "Total Quantity"})
            fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.02, x=1))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ℹ️ No data matches the selected filters.")

        # ✅ TREND CHART SECTION
        st.divider()
        st.subheader(f"📈 {user['branch']} Smahc Pull out Trend by Product")

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
            st.metric("Latest Submission", latest.strftime("%m/%d %I:%M %p"))
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
            st.session_state[key] = None if key == "qty" else "-- Full Name --" if key == "enc_name" else "-- Select Customer --" if key == "store_name" else "-- Select Product --" if key == "product" else "-- Select Unit --" if key == "uom" else ""
        st.session_state.reset_encoder_form = False

    with st.expander("📝 Add Data Here"):
        # ✅ Initialize session state defaults
        defaults = {
            "enc_name": "-- Full Name --", "store_name": "-- Select Customer --",
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
                    "timestamp": datetime.now(PHT).strftime("%Y-%m-%d %I:%M:%S %p"),
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
            st.metric("Latest Submission", latest.strftime("%m/%d %I:%M %p"))
        else:
            st.metric("Latest Submission", "N/A")
            

def render_market_survey_view(user):
    st.header("📋 Market Survey Form")
    st.caption(f"Encoder: `{user['username']}` | Branch: `{user.get('branch', 'N/A')}`")

    # Initialize session state marker
    if "ms_survey_ready" not in st.session_state:
        st.session_state.ms_survey_ready = True

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏪 Store Info", "🌾 Feeds", " Petfood", "💊 Vetmed", "✅ Review & Submit"])

    # =============================================================================
    # TAB 1: STORE INFORMATION
    # =============================================================================
    with tab1:
        st.subheader("🏪 Store Details")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Name of Store", key="ms_store_name", placeholder="e.g., ABC AGRIVET")
            st.text_input("Owner's Name", key="ms_owner_name", placeholder="e.g., JUAN DELA CRUZ")
            
            # ✅ Split Address into 3 fields
            st.text_input("Street", key="ms_street", placeholder="Street / Purok / Zone")
            st.text_input("Barangay", key="ms_barangay", placeholder="Barangay")
            st.text_input("City", key="ms_city", placeholder="City")
            st.text_input("Province", key="ms_province", placeholder="Province")
            
        with col2:
            st.text_input("Contact No.", key="ms_contact", placeholder="09XX XXX XXXX")
            st.date_input(
                "Owner's B-Day", 
                key="ms_bday",
                min_value=date(1900, 1, 1),      # ✅ Now creates a proper date object
                max_value=date.today()           # ✅ Blocks future birthdates
            )
            
            st.markdown("**Store Class (Avg. bags sold/month):**")
            c1, c2, c3 = st.columns(3)
            c1.number_input("Class A (501+)", min_value=0, step=1, key="ms_class_a")
            c2.number_input("Class B (101-500)", min_value=0, step=1, key="ms_class_b")
            c3.number_input("Class C (≤100)", min_value=0, step=1, key="ms_class_c")

        dist_type = st.selectbox("Distribution Type", ["DIRECT-SERVED", "SUB-DEALER"], key="ms_dist_type")
    
    # Initialize sub-dealer list in session state
    if "ms_direct_dealers" not in st.session_state:
        st.session_state.ms_direct_dealers = []
    
    if dist_type == "DIRECT-SERVED":
        st.markdown("**Sub-Dealers List**")
        st.caption("Add all stores serving as sub-dealers")
        
        # Input for new sub-dealer
        new_dealer = st.text_input("Add Sub-Dealer", key="ms_new_sub_dealer", placeholder="Enter store name")
        
        col_add, col_clear = st.columns([1, 3])
        with col_add:
            if st.button("➕ Add Sub-Dealer", key="ms_add_dealer_btn"):
                if new_dealer.strip():
                    st.session_state.ms_sub_dealers.append(new_dealer.strip().upper())
                    st.rerun()
                else:
                    st.warning("Please enter a store name")
        
        with col_clear:
            if st.button("🗑️ Clear All", key="ms_clear_dealers_btn"):
                st.session_state.ms_sub_dealers = []
                st.rerun()
        
        # Display added sub-dealers with remove buttons
        if st.session_state.ms_sub_dealers:
            st.divider()
            st.markdown("**Added Sub-Dealers:**")
            for i, dealer in enumerate(st.session_state.ms_sub_dealers):
                col_dealer, col_remove = st.columns([4, 1])
                with col_dealer:
                    st.text_input(f"Sub-Dealer {i+1}", value=dealer, disabled=True, key=f"ms_dealer_display_{i}")
                with col_remove:
                    if st.button("❌", key=f"ms_remove_dealer_{i}"):
                        st.session_state.ms_sub_dealers.pop(i)
                        st.rerun()

    # =============================================================================
    # TAB 2: FEEDS SURVEY
    # =============================================================================
    with tab2:
        st.subheader("🌾 Feeds Survey")
        st.caption("Enter number of bags sold per month")
        
        HOGS = ["ULTRAPAK", "PILMICO", "PIGROLAC", "UNIFEEDS", "CJ", "UNO", "PROMIX", "FEED EXPRESS", "VIEPRO", "VAST", "SUNJIN", "KARGADO", "HARVESTA", "NEW HOPE", "OTHERS"]
        GF_50 = ["GALLIMAX", "GMP", "INFINITY", "FIREBIRD", "PRO-BOOST", "AVES", "GF", "OTHERS"]
        LAYER = ["LAYEX", "PILMICO EXPRESS", "SARIMANOK", "UNIFEEDS", "UNO", "SUNJIN", "LAYENA", "GREENHILLS", "OTHERS"]
        GF_24 = ["THUNDERBIRD", "SALTO", "SAGUPAAN", "WARHAWK", "OTHERS"]
        BROILER = ["PILMICO", "GREENHILLS", "GMC", "UNIFEEDS", "OTHERS"]

        def feed_section(title, brands, cols_per_row=3):
            st.markdown(f"**{title}**")
            cols = st.columns(cols_per_row)
            for i, brand in enumerate(brands):
                with cols[i % cols_per_row]:
                    key = f"ms_feeds_{title.replace(' ', '_').lower()}_{brand.replace(' ', '_').replace('-', '_')}"
                    st.number_input(brand, min_value=0, step=1, key=key)
            st.divider()

        feed_section("HOGS (50 kg)", HOGS, 3)
        feed_section("GAMEFOWL (50 kg)", GF_50, 4)
        feed_section("LAYER (50 kg)", LAYER, 3)
        feed_section("GAMEFOWL (1X24 pack)", GF_24, 5)
        feed_section("BROILER (50 kg)", BROILER, 5)

    # =============================================================================
    # TAB 3: PETFOOD SURVEY
    # =============================================================================
    with tab3:
        st.subheader(" Petfood Survey")
        st.caption("Enter number of units sold per month")
        
        DOG = ["PEDIGREE", "TOP BREED", "BEEF PRO", "BUDDY'S CHOMP", "DERBY", "YUM YUM", "DOGGY WOGGY", "VITALITY", "ROYAL CANIN", "BOW WOW", "WOOFY", "SPECIAL DOG", "OTHERS"]
        CAT = ["TOP CAT", "WHISKAS", "DIXIE", "SPECIAL CAT", "AOZI", "ROYAL CANIN", "OTHERS"]

        col_dog, col_maint, col_cat = st.columns(3)
        with col_dog:
            st.markdown("**DOGFOOD - PUPPY**")
            for brand in DOG:
                key = f"ms_pet_dog_pup_{brand.replace(' ', '_').replace(' ', '')}"
                st.number_input(brand, min_value=0, step=1, key=key)
            
        with col_maint:   
            st.markdown("**DOGFOOD - MAINTENANCE**")
            for brand in DOG:
                key = f"ms_pet_dog_maint_{brand.replace(' ', '_').replace(chr(39), '')}"
                st.number_input(brand, min_value=0, step=1, key=key)
                
        with col_cat:
            st.markdown("**CATFOOD**")
            for brand in CAT:
                key = f"ms_pet_cat_{brand.replace(' ', '_')}"
                st.number_input(brand, min_value=0, step=1, key=key)

    # =============================================================================
    # TAB 4: VETMED SURVEY
    # =============================================================================
    with tab4:
        st.subheader("💊 VETMED Survey")
        st.caption("Indicate amount of purchase per month")
        
        VET_BRANDS = ["UNIVET", "EXCELLENCE", "LDI", "SAGUPAAN", "BATTLECOCK", "TRYCO", "OTHERS"]
        VET_CATS = ["WSP", "INJECTABLE", "DISINFECTANT", "GAMEFOWL PREP"]

        # Display column headers once
        st.markdown("**Category:**")
        header_cols = st.columns(4)
        # for i, cat in enumerate(VET_CATS):
        #     with header_cols[i]:
        #         st.markdown(f"**{cat}**")
        # st.divider()

        # Display each brand with labeled inputs
        for brand in VET_BRANDS:
            st.markdown(f"**{brand}**")
            cols = st.columns(4)
            for i, cat in enumerate(VET_CATS):
                with cols[i]:
                    key = f"ms_vet_{brand.replace(' ', '_')}_{cat.replace(' ', '_')}"
                    st.number_input(
                        cat,  # ✅ This is the label
                        min_value=0, 
                        step=1, 
                        key=key,
                        label_visibility="visible"  # ✅ Make sure labels are visible
                    )
            st.divider()

    # =============================================================================
    # TAB 5: REVIEW & SUBMIT
    # =============================================================================
    with tab5:
        st.subheader("✅ Review & Submit")
        f = st.session_state

        # 🔍 DEBUG: Temporarily show what's actually captured (remove after testing)
        st.info(f"`ms_dist_type`: {repr(f.get('ms_dist_type'))} | `class_a`: {repr(f.get('ms_class_a'))}")

        # ✅ 1. BUILD PAYLOAD WITH EXACT KEY MATCHING
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            "username": user["username"],
            # "branch": user.get("branch", ""),
            "store_name": str(f.get("ms_store_name", "")).strip().upper(),
            "owner_name": str(f.get("ms_owner_name", "")).strip().upper(),
            "street": str(f.get("ms_street", "")).strip().upper(),
            "barangay": str(f.get("ms_barangay", "")).strip().upper(),
            "province": str(f.get("ms_province", "")).strip().upper(),
            "contact_no": str(f.get("ms_contact", "")).strip(),
            "owner_bday": f.get("ms_bday", "").strftime("%Y-%m-%d") if f.get("ms_bday") else "",
            "class_a": int(f.get("ms_class_a", 0)),
            "class_b": int(f.get("ms_class_b", 0)),
            "class_c": int(f.get("ms_class_c", 0)),
            "distribution": str(f.get("ms_dist_type", "")).strip(),
        }

        # ✅ 2. SUB-DEALERS
        sub_dealers = st.session_state.get("ms_sub_dealers", [])
        payload["sub_dealer_count"] = len(sub_dealers)
        for i in range(1, 11):
            payload[f"sub_dealer_{i}"] = sub_dealers[i-1] if i <= len(sub_dealers) else ""

        # ✅ 3. FEEDS
        HOGS = ["ULTAPAK", "PILMICO", "PIGROLAC", "UNIFEEDS", "CJ", "UNO", "PROMIX", "FEED EXPRESS", "VIEPRO", "VAST", "SUNJIN", "KARGADO", "HARVESTA", "NEW HOPE", "OTHERS"]
        GF_50 = ["GALLIMAX", "GMP", "INFINITY", "FIREBIRD", "PRO-BOOST", "AVES", "GF", "OTHERS"]
        LAYER = ["LAYEX", "PILMICO EXPRESS", "SARIMANOK", "UNIFEEDS", "UNO", "SUNJIN", "LAYENA", "GREENHILLS", "OTHERS"]
        GF_24 = ["THUNDERBIRD", "SALTO", "SAGUPAAN", "WARHAWK", "OTHERS"]
        BROILER = ["PILMICO", "GREENHILLS", "GMC", "UNIFEEDS", "OTHERS"]

        # ✅ FEEDS - Clean column names (no parentheses)
        for brand in HOGS:
            key = f"ms_feeds_hogs_50_kg_{brand.replace(' ', '_').replace('-', '_')}"
            payload[f"feeds_hogs_50_kg_{brand}"] = int(f.get(key, 0))

        for brand in GF_50:
            key = f"ms_feeds_gamefowl_50_kg_{brand.replace(' ', '_').replace('-', '_')}"
            payload[f"feeds_gamefowl_50_kg_{brand}"] = int(f.get(key, 0))

        for brand in LAYER:
            key = f"ms_feeds_layer_50_kg_{brand.replace(' ', '_').replace('-', '_')}"
            payload[f"feeds_layer_50_kg_{brand}"] = int(f.get(key, 0))

        for brand in GF_24:
            key = f"ms_feeds_gamefowl_ix24_pack_{brand.replace(' ', '_').replace('-', '_')}"
            payload[f"feeds_gamefowl_ix24_pack_{brand}"] = int(f.get(key, 0))

        for brand in BROILER:
            key = f"ms_feeds_broiler_50_kg_{brand.replace(' ', '_').replace('-', '_')}"
            payload[f"feeds_broiler_50_kg_{brand}"] = int(f.get(key, 0))

        # ✅ 4. PETFOOD
        DOG = ["PEDIGREE", "TOP BREED", "BEEF PRO", "BUDDY'S CHOMP", "DERBY", "YUM YUM", "DOGGY WOGGY", "VITALITY", "ROYAL CANIN", "BOW WOW", "WOOFY", "SPECIAL DOG", "OTHERS"]
        CAT = ["TOP CAT", "WHISKAS", "DIXIE", "SPECIAL CAT", "AOZI", "ROYAL CANIN", "OTHERS"]

        for brand in DOG:
            safe = brand.replace(' ', '_').replace("'", "")
            payload[f"pet_dog_pup_{brand}"] = int(f.get(f"ms_pet_dog_pup_{safe}", 0))
            payload[f"pet_dog_maint_{brand}"] = int(f.get(f"ms_pet_dog_maint_{safe}", 0))

        for brand in CAT:
            payload[f"pet_cat_{brand}"] = int(f.get(f"ms_pet_cat_{brand.replace(' ', '_')}", 0))

        # ✅ 5. VETMED
        VET_BRANDS = ["UNIVET", "EXCELLENCE", "LDI", "SAGUPAAN", "BATTLECOCK", "TRYCO", "OTHERS"]
        VET_CATS = ["WSP", "INJECTABLE", "DISINFECTANT", "GAMEFOWL PREP"]

        for brand in VET_BRANDS:
            for cat in VET_CATS:
                key = f"ms_vet_{brand.replace(' ', '_')}_{cat.replace(' ', '_')}"
                payload[f"vet_{brand}_{cat}"] = int(f.get(key, 0))

        # ✅ VALIDATION
        errors = []
        if not payload["store_name"]: errors.append("Store Name is required")
        if not payload["owner_name"]: errors.append("Owner's Name is required")
        if payload["distribution"] == "SUB-DEALER" and payload["sub_dealer_count"] == 0:
            errors.append("Please add at least 1 Sub-Dealer")

        if errors:
            for e in errors: st.error(f" {e}")
        else:
            st.success("✅ All required fields completed.")
            if st.button("💾 Save to Google Sheets", type="primary", use_container_width=True):
                with st.spinner("Saving..."):
                    success = append_to_sheet("MARKET_SURVEY", payload)
                    if success:
                        st.success("🎉 Saved successfully!")
                        for k in list(st.session_state.keys()):
                            if k.startswith("ms_"): del st.session_state[k]
                        st.rerun()
                    else:
                        st.error("❌ Failed to save.")

