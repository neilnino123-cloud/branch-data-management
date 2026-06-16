import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import append_to_sheet, get_sheet_data, get_all_sheets_data, normalize_df_columns
from config import BRANCH_SHEETS, LEYTE_CUSTOMERS, SAMAR_CUSTOMERS, CALBAYOG_CUSTOMERS, SOLEY_CUSTOMERS, PRODUCT_LIST, LEYTE_ENCODERS, SAMAR_ENCODERS, CALBAYOG_ENCODERS, SOLEY_ENCODERS, USERS
import plotly.express as px
import json
from zoneinfo import ZoneInfo

# Define Philippine Time
PHT = ZoneInfo("Asia/Manila")

# ✅ Define which branches are Market Survey (to exclude from encoder charts)
MS_BRANCHES = ["LEYTE MS", "SAMAR MS", "CALBAYOG MS", "SOUTHERN LEYTE MS"]
ENCODER_BRANCHES = [b for b in BRANCH_SHEETS.keys() if b not in MS_BRANCHES]

def render_login_form():
    col1, col2, col3 = st.columns([4, 3, 4])
    with col2:
        with st.container(border=True, key="login_form"):
            st.write("\n")
            with st.container(horizontal=True, horizontal_alignment="center"):
                st.image("logo5 copy.png" if st.file_uploader else "logo5 copy.png", width=250)
            with st.container():
                st.header("Please login to access your account", text_alignment="center")
                with st.form("login_form", border=False):
                    username = st.text_input("Username", placeholder="Enter username")
                    password = st.text_input("Password", type="password", placeholder="Enter password")
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
                            st.warning("⚠️ Please enter both username and password.")

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
    
    # ✅ Create tabs for Encoder Data and Market Survey Data
    tab_encoder, tab_survey = st.tabs(["📊 Encoder SMAHC Pullout", "📋 Market Survey Data"])
    
    # =============================================================================
    # TAB 1: ENCODER SALES DATA
    # =============================================================================
    with tab_encoder:
        branches = ["All Branches"] + ENCODER_BRANCHES  # ✅ Only encoder branches
        selected_branch = st.selectbox("Select Branch to View", branches, key="admin_encoder_branch")
        st.write("\n")

        if selected_branch == "All Branches":
            # Get all encoder data only
            all_frames = []
            for branch in ENCODER_BRANCHES:
                df_branch = get_sheet_data(branch)
                if not df_branch.empty:
                    df_branch["source_branch"] = branch
                    all_frames.append(df_branch)
            df = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        else:
            df = get_sheet_data(selected_branch)

        df = normalize_df_columns(df)

        if not df.empty:
            st.dataframe(df, use_container_width=True)

            # 📊 DYNAMIC BAR CHART
            st.divider()
            st.subheader("📊 Sales Breakdown by Encoder & Product")

            df_prog = df.copy()
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)

            with col_f1:
                branch_options = ["All Branches"] + ENCODER_BRANCHES  # ✅ Only encoder branches
                bar_branch = st.selectbox("Filter by Branch", branch_options, key="bar_branch")

            if bar_branch != "All Branches" and "source_branch" in df_prog.columns:
                df_prog = df_prog[df_prog["source_branch"] == bar_branch]

            with col_f2:
                enc_col = next((c for c in ["enc_name", "encoder", "fullname", "full_name", "name"] if c in df_prog.columns), None)
                encoders = ["All Encoders"]
                if enc_col and not df_prog.empty:
                    enc_list = df_prog[enc_col].dropna().astype(str).str.strip().unique().tolist()
                    encoders += sorted([e for e in enc_list if e])
                bar_encoder = st.selectbox("Filter by Encoder", encoders, key="bar_encoder")

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

            if bar_product != "All Products":
                df_prog = df_prog[df_prog["product"] == bar_product]

            if isinstance(bar_date, tuple) and len(bar_date) == 2:
                df_prog["temp_date"] = pd.to_datetime(df_prog["timestamp"], errors="coerce").dt.date
                df_prog = df_prog[(df_prog["temp_date"] >= bar_date[0]) & (df_prog["temp_date"] <= bar_date[1])]
                df_prog.drop(columns=["temp_date"], inplace=True)

            if not df_prog.empty:
                x_axis = "product" if bar_encoder != "All Encoders" and enc_col else (enc_col if enc_col else "product")
                color_axis = "product" if bar_encoder == "All Encoders" or not enc_col else None

                group_cols = [x_axis] + ([color_axis] if color_axis else [])
                chart_df = df_prog.groupby(group_cols)["quantity"].sum().reset_index().rename(columns={"quantity": "total_qty"})

                title = f"Sales Breakdown - {bar_encoder}" if bar_encoder != "All Encoders" else f"Sales Breakdown - {bar_branch}"
                
                fig = px.bar(chart_df, x=x_axis, y="total_qty", color=color_axis, barmode="group", 
                            title=title, height=400, labels={"total_qty": "Total Quantity", "product": "Product"})
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.02, x=1), bargap=0.15)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ℹ️ No data matches the selected filters.")

            # 📈 TREND CHART
            st.divider()
            st.subheader("📈 Sales Trend by Product")

            all_products = ["All Products"] + sorted(df["product"].dropna().unique().tolist()) if "product" in df.columns else ["All Products"]
            selected_chart_product = st.selectbox("Filter by Product (Optional)", all_products, key="admin_chart_product")

            chart_df = prepare_trend_data(df, branch_filter=selected_branch)

            if not chart_df.empty:
                if selected_chart_product != "All Products":
                    chart_df = chart_df[chart_df["product"] == selected_chart_product]

                if not chart_df.empty:
                    fig = px.line(chart_df, x="date", y="quantity",
                                color="product" if selected_chart_product == "All Products" else None,
                                markers=True,
                                title=f"Sales Trend - {selected_branch}" if selected_branch != "All Branches" else "Sales Trend - All Branches",
                                labels={"quantity": "Total Quantity", "date": "Date", "product": "Product", "branch": "Branch"},
                                height=400)
                    fig.update_layout(hovermode="x unified",
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                    xaxis_title="Date", yaxis_title="Total Quantity")
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
                latest = pd.to_datetime(df["timestamp"], errors='coerce').max()
                if pd.notna(latest):
                    if latest.tzinfo is None:
                        latest = latest.tz_localize('Asia/Manila')
                    st.metric("Latest Submission", latest.strftime("%m/%d %I:%M %p"))
                else:
                    st.metric("Latest Submission", "N/A")
            else:
                st.metric("Latest Submission", "N/A")

    # =============================================================================
    # TAB 2: MARKET SURVEY DATA
    # =============================================================================
    with tab_survey:
        st.subheader("📋 Market Survey Data")
        
        survey_branches = ["All Market Survey Branches"] + MS_BRANCHES
        selected_survey_branch = st.selectbox("Select Market Survey Branch", survey_branches, key="admin_survey_branch")
        st.write("\n")

        if selected_survey_branch == "All Market Survey Branches":
            all_survey_frames = []
            for branch in MS_BRANCHES:
                df_survey = get_sheet_data(branch)
                if not df_survey.empty:
                    df_survey["source_branch"] = branch
                    all_survey_frames.append(df_survey)
            df_survey_all = pd.concat(all_survey_frames, ignore_index=True) if all_survey_frames else pd.DataFrame()
        else:
            df_survey_all = get_sheet_data(selected_survey_branch)

        df_survey_all = normalize_df_columns(df_survey_all)

        if not df_survey_all.empty:
            st.dataframe(df_survey_all, use_container_width=True)
            
            # ✅ Market Survey Analytics
            st.divider()
            st.subheader("📊 Market Survey Analytics")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Surveys", len(df_survey_all))
            with col2:
                if "distribution" in df_survey_all.columns:
                    direct_count = len(df_survey_all[df_survey_all["distribution"] == "DIRECT-SERVED"])
                    st.metric("Direct-Served", direct_count)
            with col3:
                if "distribution" in df_survey_all.columns:
                    sub_count = len(df_survey_all[df_survey_all["distribution"] == "SUB-DEALER"])
                    st.metric("Sub-Dealer", sub_count)
            with col4:
                if "store_name" in df_survey_all.columns:
                    unique_stores = df_survey_all["store_name"].nunique()
                    st.metric("Unique Stores", unique_stores)
            
            # Distribution Type Chart
            if "distribution" in df_survey_all.columns:
                st.divider()
                st.subheader("📊 Distribution Type Breakdown")
                dist_counts = df_survey_all["distribution"].value_counts().reset_index()
                dist_counts.columns = ["Distribution Type", "Count"]
                
                fig = px.pie(dist_counts, values="Count", names="Distribution Type", 
                            title="Distribution Type Distribution",
                            color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            # Store Class Chart
            if all(col in df_survey_all.columns for col in ["class_a", "class_b", "class_c"]):
                st.divider()
                st.subheader("📊 Store Class Distribution")
                
                # ✅ FIX: Use pd.to_numeric to handle empty strings safely
                class_a_count = (pd.to_numeric(df_survey_all["class_a"], errors='coerce').fillna(0).astype(int) > 0).sum()
                class_b_count = (pd.to_numeric(df_survey_all["class_b"], errors='coerce').fillna(0).astype(int) > 0).sum()
                class_c_count = (pd.to_numeric(df_survey_all["class_c"], errors='coerce').fillna(0).astype(int) > 0).sum()
                
                class_data = {
                    "Class": ["Class A (501+)", "Class B (101-500)", "Class C (≤100)"],
                    "Count": [class_a_count, class_b_count, class_c_count]
                }
                class_df = pd.DataFrame(class_data)
                
                fig = px.bar(class_df, x="Class", y="Count", 
                            title="Number of Stores by Class",
                            color="Class",
                            color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
            # Top Feeds Brands
            feed_cols = [col for col in df_survey_all.columns if col.startswith("feeds_hogs_50_kg_")]
            if feed_cols:
                st.divider()
                st.subheader("🌾 Top Hog Feeds Brands (50kg)")
                
                brand_totals = {}
                for col in feed_cols:
                    brand_name = col.replace("feeds_hogs_50_kg_", "").replace("_", " ").title()
                    total = pd.to_numeric(df_survey_all[col], errors="coerce").sum()
                    if total > 0:
                        brand_totals[brand_name] = total
                
                if brand_totals:
                    brand_df = pd.DataFrame(list(brand_totals.items()), columns=["Brand", "Total Bags"])
                    brand_df = brand_df.sort_values("Total Bags", ascending=False).head(10)
                    
                    fig = px.bar(brand_df, x="Brand", y="Total Bags", 
                                title="Top 10 Hog Feeds Brands by Total Bags Sold",
                                color="Total Bags",
                                color_continuous_scale="Blues")
                    fig.update_layout(height=400, xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ℹ️ No market survey data available.")
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Surveys", len(df_survey_all))
        with col2:
            if "timestamp" in df_survey_all.columns and not df_survey_all["timestamp"].isna().all():
                latest = pd.to_datetime(df_survey_all["timestamp"], errors='coerce').max()
                if pd.notna(latest):
                    if latest.tzinfo is None:
                        latest = latest.tz_localize('Asia/Manila')
                    st.metric("Latest Survey", latest.strftime("%m/%d %I:%M %p"))
                else:
                    st.metric("Latest Survey", "N/A")
            else:
                st.metric("Latest Survey", "N/A")


def render_moderator_view(user):
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.header(f"👨‍💼 Moderator Dashboard: {user['branch']}")
        if st.button("🔄 Refresh Data", type="secondary"):
            get_sheet_data.clear()
            get_all_sheets_data.clear()
            st.rerun()

    # ✅ Check if moderator is for encoder branch or market survey branch
    is_ms_branch = user["branch"] in MS_BRANCHES
    
    # Create appropriate tabs
    if is_ms_branch:
        tab_survey = st.tabs(["📋 Market Survey Data"])[0]
        
        with tab_survey:
            # st.divider()
            st.subheader("📝 All Market Surveys")
            st.caption("Complete market survey history")

            df = get_sheet_data(user["branch"])
            df = normalize_df_columns(df)
            df_display = df.drop(columns=["username"], errors="ignore")

            if not df.empty:
                st.dataframe(df_display, use_container_width=True)
                
                # ✅ Market Survey Analytics for Moderator
                st.divider()
                st.subheader(f"📊 {user['branch']} Market Survey Analytics")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Surveys", len(df))
                with col2:
                    if "distribution" in df.columns:
                        direct_count = len(df[df["distribution"] == "DIRECT-SERVED"])
                        st.metric("Direct-Served", direct_count)
                with col3:
                    if "distribution" in df.columns:
                        sub_count = len(df[df["distribution"] == "SUB-DEALER"])
                        st.metric("Sub-Dealer", sub_count)
                with col4:
                    if "store_name" in df.columns:
                        unique_stores = df["store_name"].nunique()
                        st.metric("Unique Stores", unique_stores)
                
                # Distribution Type Chart
                if "distribution" in df.columns:
                    st.divider()
                    st.subheader("📊 Distribution Type Breakdown")
                    dist_counts = df["distribution"].value_counts().reset_index()
                    dist_counts.columns = ["Distribution Type", "Count"]
                    
                    fig = px.pie(dist_counts, values="Count", names="Distribution Type", 
                                title=f"{user['branch']} - Distribution Type",
                                color_discrete_sequence=px.colors.qualitative.Set2)
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Store Class Chart
                if all(col in df.columns for col in ["class_a", "class_b", "class_c"]):
                    st.divider()
                    st.subheader("📊 Store Class Distribution")
                    
                    # ✅ FIX: Use pd.to_numeric to handle empty strings safely
                    class_a_count = (pd.to_numeric(df["class_a"], errors='coerce').fillna(0).astype(int) > 0).sum()
                    class_b_count = (pd.to_numeric(df["class_b"], errors='coerce').fillna(0).astype(int) > 0).sum()
                    class_c_count = (pd.to_numeric(df["class_c"], errors='coerce').fillna(0).astype(int) > 0).sum()
                    
                    class_data = {
                        "Class": ["Class A (501+)", "Class B (101-500)", "Class C (≤100)"],
                        "Count": [class_a_count, class_b_count, class_c_count]
                    }
                    class_df = pd.DataFrame(class_data)
                    
                    fig = px.bar(class_df, x="Class", y="Count", 
                                title=f"{user['branch']} - Store Classes",
                                color="Class",
                                color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Top Feeds Brands
                feed_cols = [col for col in df.columns if col.startswith("feeds_hogs_50_kg_")]
                if feed_cols:
                    st.divider()
                    st.subheader("🌾 Top Hog Feeds Brands (50kg)")
                    
                    brand_totals = {}
                    for col in feed_cols:
                        brand_name = col.replace("feeds_hogs_50_kg_", "").replace("_", " ").title()
                        total = pd.to_numeric(df[col], errors="coerce").sum()
                        if total > 0:
                            brand_totals[brand_name] = total
                    
                    if brand_totals:
                        brand_df = pd.DataFrame(list(brand_totals.items()), columns=["Brand", "Total Bags"])
                        brand_df = brand_df.sort_values("Total Bags", ascending=False).head(10)
                        
                        fig = px.bar(brand_df, x="Brand", y="Total Bags", 
                                    title=f"{user['branch']} - Top 10 Hog Feeds Brands",
                                    color="Total Bags",
                                    color_continuous_scale="Blues")
                        fig.update_layout(height=400, xaxis_tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ℹ️ No market survey records yet.")

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Surveys", len(df))
            with col2:
                if "timestamp" in df.columns and not df["timestamp"].isna().all():
                    latest = pd.to_datetime(df["timestamp"], errors='coerce').max()
                    if pd.notna(latest):
                        if latest.tzinfo is None:
                            latest = latest.tz_localize('Asia/Manila')
                        st.metric("Latest Survey", latest.strftime("%m/%d %I:%M %p"))
                    else:
                        st.metric("Latest Survey", "N/A")
                else:
                    st.metric("Latest Survey", "N/A")
    else:
        # Encoder branch moderator
        tab_encoder, tab_survey = st.tabs(["📊 Encoder SMAHC Pullout", "📋 Market Survey Data"])
        
        with tab_encoder:
            # st.divider()
            st.subheader("📝 All Transactions")
            st.caption("Complete transaction history")

            df = get_sheet_data(user["branch"])
            df = normalize_df_columns(df)
            df_display = df.drop(columns=["username"], errors="ignore")

            if not df.empty:
                st.dataframe(df_display, use_container_width=True)
                
                # 📊 MODERATOR: DYNAMIC SALES BREAKDOWN
                st.divider()
                st.subheader(f"📊 {user['branch']} Sales Breakdown")

                df_prog = df.copy()
                col_f1, col_f2, col_f3 = st.columns(3)

                with col_f1:
                    enc_col = next((c for c in ["enc_name", "encoder", "fullname", "full_name", "name"] if c in df_prog.columns), None)
                    encoders = ["All Encoders"]
                    if enc_col and not df_prog.empty:
                        enc_list = df_prog[enc_col].dropna().astype(str).str.strip().unique().tolist()
                        encoders += sorted([e for e in enc_list if e])
                    bar_encoder = st.selectbox("Filter by Encoder", encoders, key=f"mod_bar_enc_{user['branch']}")

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

                if bar_product != "All Products":
                    df_prog = df_prog[df_prog["product"] == bar_product]
                if isinstance(bar_date, tuple) and len(bar_date) == 2:
                    df_prog["temp_date"] = pd.to_datetime(df_prog["timestamp"], errors="coerce").dt.date
                    df_prog = df_prog[(df_prog["temp_date"] >= bar_date[0]) & (df_prog["temp_date"] <= bar_date[1])]
                    df_prog.drop(columns=["temp_date"], inplace=True)

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

                # 📈 TREND CHART
                st.divider()
                st.subheader(f"📈 {user['branch']} Sales Trend by Product")

                all_products = ["All Products"] + sorted(df["product"].dropna().unique().tolist()) if "product" in df.columns else ["All Products"]
                selected_chart_product = st.selectbox("Filter by Product (Optional)", all_products, key=f"mod_chart_product_{user['branch']}")

                chart_df = prepare_trend_data(df, branch_filter=user["branch"])

                if not chart_df.empty:
                    if selected_chart_product != "All Products":
                        chart_df = chart_df[chart_df["product"] == selected_chart_product]

                    if not chart_df.empty:
                        fig = px.line(chart_df, x="date", y="quantity", color="product", markers=True,
                                    title=f"{user['branch']} - Sales Trend",
                                    labels={"quantity": "Total Quantity", "date": "Date", "product": "Product"},
                                    height=400)
                        fig.update_layout(hovermode="x unified",
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
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
                    latest = pd.to_datetime(df["timestamp"], errors='coerce').max()
                    if pd.notna(latest):
                        if latest.tzinfo is None:
                            latest = latest.tz_localize('Asia/Manila')
                        st.metric("Latest Submission", latest.strftime("%m/%d %I:%M %p"))
                    else:
                        st.metric("Latest Submission", "N/A")
                else:
                    st.metric("Latest Submission", "N/A")
        
        with tab_survey:
            st.subheader("📋 Market Survey Data")
            st.caption(f"Viewing market survey data for {user['branch']}")
            
            # Map encoder branch to corresponding MS branch
            ms_branch_map = {
                "TWMC LEYTE": "LEYTE MS",
                "TWMC SAMAR": "SAMAR MS",
                "TWMC CALBAYOG": "CALBAYOG MS",
                "TWMC SOUTHERN LEYTE": "SOUTHERN LEYTE MS"
            }
            
            ms_branch = ms_branch_map.get(user["branch"])
            
            if ms_branch:
                df_survey = get_sheet_data(ms_branch)
                df_survey = normalize_df_columns(df_survey)
                
                if not df_survey.empty:
                    st.dataframe(df_survey, use_container_width=True)
                    
                    # Analytics
                    st.divider()
                    st.subheader(f"📊 {ms_branch} Market Survey Analytics")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Surveys", len(df_survey))
                    with col2:
                        if "distribution" in df_survey.columns:
                            direct_count = len(df_survey[df_survey["distribution"] == "DIRECT-SERVED"])
                            st.metric("Direct-Served", direct_count)
                    with col3:
                        if "distribution" in df_survey.columns:
                            sub_count = len(df_survey[df_survey["distribution"] == "SUB-DEALER"])
                            st.metric("Sub-Dealer", sub_count)
                    with col4:
                        if "store_name" in df_survey.columns:
                            unique_stores = df_survey["store_name"].nunique()
                            st.metric("Unique Stores", unique_stores)
                    
                    # Distribution Chart
                    if "distribution" in df_survey.columns:
                        st.divider()
                        st.subheader("📊 Distribution Type Breakdown")
                        dist_counts = df_survey["distribution"].value_counts().reset_index()
                        dist_counts.columns = ["Distribution Type", "Count"]
                        
                        fig = px.pie(dist_counts, values="Count", names="Distribution Type", 
                                    title=f"{ms_branch} - Distribution Type",
                                    color_discrete_sequence=px.colors.qualitative.Set2)
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Store Class Chart
                    if all(col in df_survey.columns for col in ["class_a", "class_b", "class_c"]):
                        st.divider()
                        st.subheader("📊 Store Class Distribution")
                        
                        class_a_count = (pd.to_numeric(df_survey["class_a"], errors='coerce').fillna(0).astype(int) > 0).sum()
                        class_b_count = (pd.to_numeric(df_survey["class_b"], errors='coerce').fillna(0).astype(int) > 0).sum()
                        class_c_count = (pd.to_numeric(df_survey["class_c"], errors='coerce').fillna(0).astype(int) > 0).sum()
                        
                        class_data = {
                            "Class": ["Class A (501+)", "Class B (101-500)", "Class C (≤100)"],
                            "Count": [class_a_count, class_b_count, class_c_count]
                        }
                        class_df = pd.DataFrame(class_data)
                        
                        fig = px.bar(class_df, x="Class", y="Count", 
                                    title=f"{ms_branch} - Store Classes",
                                    color="Class",
                                    color_discrete_sequence=px.colors.qualitative.Pastel)
                        fig.update_layout(height=400, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Top Feeds Brands
                    feed_cols = [col for col in df_survey.columns if col.startswith("feeds_hogs_50_kg_")]
                    if feed_cols:
                        st.divider()
                        st.subheader("🌾 Top Hog Feeds Brands (50kg)")
                        
                        brand_totals = {}
                        for col in feed_cols:
                            brand_name = col.replace("feeds_hogs_50_kg_", "").replace("_", " ").title()
                            total = pd.to_numeric(df_survey[col], errors="coerce").sum()
                            if total > 0:
                                brand_totals[brand_name] = total
                        
                        if brand_totals:
                            brand_df = pd.DataFrame(list(brand_totals.items()), columns=["Brand", "Total Bags"])
                            brand_df = brand_df.sort_values("Total Bags", ascending=False).head(10)
                            
                            fig = px.bar(brand_df, x="Brand", y="Total Bags", 
                                        title=f"{ms_branch} - Top 10 Hog Feeds Brands",
                                        color="Total Bags",
                                        color_continuous_scale="Blues")
                            fig.update_layout(height=400, xaxis_tickangle=-45)
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("ℹ️ No market survey data available for this branch.")
            else:
                st.warning("⚠️ No corresponding market survey branch found.")


def get_encode_list(branch: str, team: str = None) -> list[str]:
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

    if isinstance(source, dict):
        if team:
            team_key = next((k for k, v in USERS.items()
                if v.get("branch") == branch and v.get("team") == team), None)
            if team_key and team_key in source:
                val = source[team_key]
                names.update(val if isinstance(val, (set, list)) else {val})
            else:
                for val in source.values():
                    names.update(val if isinstance(val, (set, list)) else {val})

    elif isinstance(source, list):
        names.update(n for n in source if n and not n.startswith("--"))

    return ["-- Full Name --"] + sorted(names) if names else ["-- Full Name --"]


def render_encoder_view(user):
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.header(f"⌨️ Sales Portal: {user.get('team', 'General')}")
        if st.button("🔄 Refresh Data", type="secondary"):
            get_sheet_data.clear()
            get_all_sheets_data.clear()
            st.rerun()

    if user["branch"]:
        selected_branch = user["branch"]
        st.info(f"🔒 Assigned to: {selected_branch}")
    else:
        selected_branch = st.selectbox("Select Target Branch", list(BRANCH_SHEETS.keys()))

    if st.session_state.get("reset_encoder_form", False):
        st.session_state.enc_name = "-- Full Name --"
        st.session_state.store_name = "-- Select Customer --"
        st.session_state.product = "-- Select Product --"
        st.session_state.uom = "-- Select Unit --"
        st.session_state.qty = 0
        st.session_state.notes = ""
        st.session_state.reset_encoder_form = False

    with st.expander("📝 Add Data Here"):
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

        emp_list = get_encode_list(user["branch"], user.get("team"))
        st.selectbox("Full Name", emp_list, key="enc_name")

        customer_list = {
            "TWMC LEYTE": LEYTE_CUSTOMERS,
            "TWMC SAMAR": SAMAR_CUSTOMERS,
            "TWMC CALBAYOG": CALBAYOG_CUSTOMERS,
            "TWMC SOUTHERN LEYTE": SOLEY_CUSTOMERS
        }.get(selected_branch, ["-- Select Customer --"])

        st.selectbox("Enter Store Name", customer_list, key="store_name")

        product_options = ["-- Select Product --"] + list(PRODUCT_LIST.keys())
        st.selectbox("Product", product_options, key="product")

        selected_product = st.session_state.product
        if selected_product in ("-- Select Product --", "-- OTHERS --") or not PRODUCT_LIST.get(selected_product):
            uom_options = ["-- Select Unit --"]
        else:
            uom_options = ["-- Select Unit --"] + sorted(PRODUCT_LIST[selected_product])
        st.selectbox("UOM", uom_options, key="uom")

        st.number_input("Quantity", min_value=0, step=1, key="qty")
        st.text_area("Notes", key="notes")

        if st.button("Submit Data"):
            errors = []
            if st.session_state.enc_name == "-- Full Name --":
                errors.append("Please enter your name")
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
                    "timestamp": datetime.now(PHT).strftime("%Y-%m-%d %H:%M:%S"),
                    "username": user["username"],
                    "role_team": f"Encoder - {user.get('team', 'General')}",
                    "name": st.session_state.enc_name.strip().upper(),
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
            latest = pd.to_datetime(df["timestamp"], errors='coerce').max()
            if pd.notna(latest):
                if latest.tzinfo is None:
                    latest = latest.tz_localize('Asia/Manila')
                st.metric("Latest Submission", latest.strftime("%m/%d %I:%M %p"))
            else:
                st.metric("Latest Submission", "N/A")
        else:
            st.metric("Latest Submission", "N/A")


def prepare_trend_data(df: pd.DataFrame, branch_filter: str = None) -> pd.DataFrame:
    """Prepares dataframe for trend line chart with normalized columns."""
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

    required = ["timestamp", "product", "quantity"]
    if not all(col in df.columns for col in required):
        return pd.DataFrame()

    if branch_filter and branch_filter != "All Branches":
        if "source_branch" in df.columns:
            df = df[df["source_branch"] == branch_filter]

    df["date"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.date
    df = df.dropna(subset=["date", "product", "quantity"])

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
    
    enc_col = None
    for col in ["enc_name", "encoder", "encoder_name", "fullname"]:
        if col in df.columns:
            enc_col = col
            break
    
    required = ["timestamp", "product", "quantity"]
    if enc_col:
        required.append(enc_col)
        
    if not all(col in df.columns for col in required):
        if not all(col in df.columns for col in ["timestamp", "product", "quantity"]):
            return pd.DataFrame()
    
    if branch_filter and branch_filter != "All Branches" and "source_branch" in df.columns:
        df = df[df["source_branch"] == branch_filter]
    
    if encoder_filter and encoder_filter != "All Encoders" and enc_col:
        df = df[df[enc_col] == encoder_filter]
    
    if product_filter and product_filter != "All Products":
        df = df[df["product"] == product_filter]
    
    if date_range and date_range[0] and date_range[1]:
        df["date_only"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.date
        df = df[(df["date_only"] >= date_range[0]) & (df["date_only"] <= date_range[1])]
    
    group_cols = [enc_col, "product"] if enc_col else ["product"]
    if "source_branch" in df.columns and branch_filter == "All Branches":
        group_cols.append("source_branch")
    
    grouped = df.groupby(group_cols + ["date_only"])["quantity"].sum().reset_index()
    grouped = grouped.rename(columns={"date_only": "date", "quantity": "total_qty"})
    return grouped


def render_market_survey_view(user):
    st.header("📋 Market Survey Form")
    st.caption(f"Encoder: `{user['username']}` | Branch: `{user.get('branch', 'N/A')}` | Team: `{user.get('team', 'N/A')}`")

    if "ms_initialized" not in st.session_state:
        st.session_state.ms_initialized = True
        st.session_state.ms_save_success = False
        st.session_state.ms_attempted_submit = False
        
        st.session_state.ms_store_name = ""
        st.session_state.ms_owner_name = ""
        st.session_state.ms_street = ""
        st.session_state.ms_barangay = ""
        st.session_state.ms_city = ""
        st.session_state.ms_province = ""
        st.session_state.ms_contact = ""
        st.session_state.ms_bday = date.today()
        st.session_state.ms_class_a = 0
        st.session_state.ms_class_b = 0
        st.session_state.ms_class_c = 0
        st.session_state.ms_dist_type = "DIRECT-SERVED"
        st.session_state.ms_direct_dealers = []
        
        HOGS = ["ULTRAPAK", "PILMICO", "PIGROLAC", "UNIFEEDS", "CJ", "UNO", "PROMIX", "FEED EXPRESS", "VIEPRO", "VAST", "SUNJIN", "KARGADO", "HARVESTA", "NEW HOPE", "OTHERS"]
        GF_50 = ["GALLIMAX", "GMP", "INFINITY", "FIREBIRD", "PRO-BOOST", "AVES", "GF", "OTHERS"]
        LAYER = ["LAYEX", "PILMICO EXPRESS", "SARIMANOK", "UNIFEEDS", "UNO", "SUNJIN", "LAYENA", "GREENHILLS", "OTHERS"]
        GF_24 = ["THUNDERBIRD", "SALTO", "SAGUPAAN", "WARHAWK", "OTHERS"]
        BROILER = ["PILMICO", "GREENHILLS", "GMC", "UNIFEEDS", "OTHERS"]
        DOG = ["PEDIGREE", "TOP BREED", "BEEF PRO", "BUDDY'S CHOMP", "DERBY", "YUM YUM", "DOGGY WOGGY", "VITALITY", "ROYAL CANIN", "BOW WOW", "WOOFY", "SPECIAL DOG", "OTHERS"]
        CAT = ["TOP CAT", "WHISKAS", "DIXIE", "SPECIAL CAT", "AOZI", "ROYAL CANIN", "OTHERS"]
        VET_BRANDS = ["UNIVET", "EXCELLENCE", "LDI", "SAGUPAAN", "BATTLECOCK", "TRYCO", "OTHERS"]
        VET_CATS = ["WSP", "INJECTABLE", "DISINFECTANT", "GAMEFOWL_PREP"]

        for prefix, brands in [("hogs_50_kg", HOGS), ("gamefowl_50_kg", GF_50), ("layer_50_kg", LAYER), ("gamefowl_ix24_pack", GF_24), ("broiler_50_kg", BROILER)]:
            for brand in brands:
                st.session_state[f"ms_feeds_{prefix}_{brand.replace(' ', '_').replace('-', '_')}"] = 0

        for brand in DOG:
            safe = brand.replace(' ', '_')
            st.session_state[f"ms_pet_dog_pup_{safe}"] = 0
            st.session_state[f"ms_pet_dog_maint_{safe}"] = 0

        for brand in CAT:
            st.session_state[f"ms_pet_cat_{brand.replace(' ', '_')}"] = 0

        for brand in VET_BRANDS:
            for cat in VET_CATS:
                st.session_state[f"ms_vet_{brand.replace(' ', '_')}_{cat.replace(' ', '_')}"] = 0

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏪 Store Info", "🌾 Feeds", "🐾 Petfood", "💊 Vetmed", "✅ Review & Submit"])

    with tab1:
        st.subheader("🏪 Store Details")
        col1, col2 = st.columns(2)
        
        # Validation flags
        validation_errors = []
        
        with col1:
            # Store Name - Required first field
            store_name_input = st.text_input("Name of Store *", key="ms_store_name", placeholder="e.g., ABC AGRIVET")
            if not store_name_input.strip():
                validation_errors.append("Store Name is required")
            
            # Owner's Name - Required, only after Store Name is filled
            if store_name_input.strip():
                owner_name_input = st.text_input("Owner's Name *", key="ms_owner_name", placeholder="e.g., JUAN DELA CRUZ")
                if not owner_name_input.strip():
                    validation_errors.append("Owner's Name is required")
            else:
                owner_name_input = st.text_input("Owner's Name *", key="ms_owner_name", placeholder="e.g., JUAN DELA CRUZ", disabled=True)
                validation_errors.append("Please fill in Store Name first")
            
            # Street - Required, only after Owner's Name is filled
            if owner_name_input.strip():
                street_input = st.text_input("Street", key="ms_street", placeholder="Street / Purok / Zone")
            else:
                street_input = st.text_input("Street", key="ms_street", placeholder="Street / Purok / Zone", disabled=True)
            
            # Barangay - Required, only after Street is filled
            if street_input.strip():
                barangay_input = st.text_input("Barangay *", key="ms_barangay", placeholder="Barangay")
                if not barangay_input.strip():
                    validation_errors.append("Barangay is required")
            else:
                barangay_input = st.text_input("Barangay *", key="ms_barangay", placeholder="Barangay", disabled=True)
                if owner_name_input.strip():  # Only show error if previous field is filled
                    validation_errors.append("Please fill in Street first")
            
            # City - Required, only after Barangay is filled
            if barangay_input.strip():
                city_input = st.text_input("City *", key="ms_city", placeholder="City")
                if not city_input.strip():
                    validation_errors.append("City is required")
            else:
                city_input = st.text_input("City *", key="ms_city", placeholder="City", disabled=True)
                validation_errors.append("Please fill in Barangay first")
            
            # Province - Required, only after City is filled
            if city_input.strip():
                province_input = st.text_input("Province *", key="ms_province", placeholder="Province")
                if not province_input.strip():
                    validation_errors.append("Province is required")
            else:
                province_input = st.text_input("Province *", key="ms_province", placeholder="Province", disabled=True)
                validation_errors.append("Please fill in City first")
            
        with col2:
            # --- Helper function to force numbers only ---
            def sanitize_contact_input():
                # Get current value
                val = st.session_state.get("ms_contact", "")
                # Keep only digits (0-9)
                sanitized = ''.join(c for c in val if c.isdigit())
                # Update session state if it changed
                if sanitized != val:
                    st.session_state.ms_contact = sanitized

            # Contact No. - Required, only after Province is filled
            if province_input.strip():
                contact_input = st.text_input(
                    "Contact No. * (Numbers only)", 
                    key="ms_contact", 
                    placeholder="09XXXXXXXXX",
                    on_change=sanitize_contact_input, # ✅ Forces numbers only
                    help="Please enter digits only (e.g., 09171234567)"
                )
                
                # Validate format after sanitization
                if contact_input.strip():
                    if not contact_input.startswith("09"):
                        validation_errors.append("Mobile number must start with '09'")
                    elif len(contact_input) != 11:
                        validation_errors.append("Mobile number must be exactly 11 digits")
                else:
                    validation_errors.append("Contact Number is required")
            else:
                contact_input = st.text_input("Contact No. *", key="ms_contact", placeholder="09XX XXX XXXX", disabled=True)
                validation_errors.append("Please fill in Province first")
            
            # Owner's B-Day - Required, only after Contact No. is filled and valid, age must be >= 20
            if contact_input.strip() and len(validation_errors) == 0 or (contact_input.strip() and "Contact No." not in str(validation_errors)):
                bday_input = st.date_input("Owner's B-Day *", key="ms_bday", min_value=date(1900, 1, 1), max_value=date.today())
                
                # Calculate age
                if bday_input:
                    today = date.today()
                    age = today.year - bday_input.year - ((today.month, today.day) < (bday_input.month, bday_input.day))
                    
                    if age < 20:
                        validation_errors.append(f"Owner must be at least 20 years old (current age: {age})")
            else:
                bday_input = st.date_input("Owner's B-Day *", key="ms_bday", min_value=date(1900, 1, 1), max_value=date.today(), disabled=True)
                if contact_input.strip():
                    validation_errors.append("Please enter a valid Contact Number first")
            
            st.markdown("**Store Class (Avg. bags sold/month):**")
            c1, c2, c3 = st.columns(3)

            # ✅ Safely define bday_valid here to prevent NameError
            bday_val_state = st.session_state.get("ms_bday")
            age_error_exists = any("20 years old" in e for e in validation_errors)
            bday_valid = bool(bday_val_state) and not age_error_exists

            if bday_valid:
                class_a_input = c1.number_input("Class A (501+)", min_value=0, step=1, key="ms_class_a", help="Enter number of bags sold (must be 501 or more)")
            else:
                class_a_input = c1.number_input("Class A (501+)", min_value=0, step=1, key="ms_class_a", disabled=True)

            if bday_valid:
                class_b_input = c2.number_input("Class B (101-500)", min_value=0, step=1, key="ms_class_b", help="Enter number of bags sold (101-500)")
            else:
                class_b_input = c2.number_input("Class B (101-500)", min_value=0, step=1, key="ms_class_b", disabled=True)

            if bday_valid:
                class_c_input = c3.number_input("Class C (≤100)", min_value=0, step=1, key="ms_class_c", help="Enter number of bags sold (0-100)")
            else:
                class_c_input = c3.number_input("Class C (≤100)", min_value=0, step=1, key="ms_class_c", disabled=True)

            # ✅ Validate: Only ONE class should have a value
            classes_filled = sum([1 for x in [class_a_input, class_b_input, class_c_input] if x > 0])
            
            if classes_filled > 1:
                validation_errors.append("⚠️ Please fill in ONLY ONE Store Class (A, B, or C), not multiple classes")
            elif classes_filled == 1:
                # Validate the range of the filled class
                if class_a_input > 0 and class_a_input < 501:
                    validation_errors.append("Class A must be 501 or more bags")
                if class_b_input > 0 and (class_b_input < 101 or class_b_input > 500):
                    validation_errors.append("Class B must be between 101 and 500 bags")
                if class_c_input > 100:
                    validation_errors.append("Class C must be 100 bags or less")

        # Distribution Type - Always available
        st.selectbox("Distribution Type *", ["DIRECT-SERVED", "SUB-DEALER"], key="ms_dist_type")
        
        # Show validation errors at the top of the tab
        if validation_errors:
            st.error("⚠️ Please correct the following errors:")
            for error in validation_errors:
                st.text(f"• {error}")
    
    if st.session_state.ms_dist_type == "DIRECT-SERVED":
        with tab1:
            st.divider()
            st.markdown("**Sub-Dealers List**")
            st.caption("Add all stores serving as sub-dealers")
            
            new_dealer = st.text_input("Add Sub-Dealer", key="ms_new_sub_dealer_input", placeholder="Enter store name")
            
            col_add, col_clear = st.columns([1, 3])
            with col_add:
                if st.button("➕ Add Sub-Dealer", key="ms_add_dealer_btn"):
                    if new_dealer.strip():
                        st.session_state.ms_direct_dealers.append(new_dealer.strip().upper())
                        st.rerun()
                    else:
                        st.warning("Please enter a store name")
            
            with col_clear:
                if st.button("🗑️ Clear All", key="ms_clear_dealers_btn"):
                    st.session_state.ms_direct_dealers = []
                    st.rerun()
            
            if st.session_state.ms_direct_dealers:
                st.divider()
                st.markdown("**Added Sub-Dealers:**")
                for i, dealer in enumerate(st.session_state.ms_direct_dealers):
                    col_dealer, col_remove = st.columns([4, 1])
                    with col_dealer:
                        st.text(f"Sub-Dealer {i+1}: {dealer}")
                    with col_remove:
                        if st.button("❌", key=f"ms_remove_dealer_{i}"):
                            st.session_state.ms_direct_dealers.pop(i)
                            st.rerun()

    with tab2:
        st.subheader("🌾 Feeds Survey")
        st.caption("Enter number of bags sold per month")

        def feed_section(title, key_prefix, brands, cols_per_row=3):
            st.markdown(f"**{title}**")
            cols = st.columns(cols_per_row)
            for i, brand in enumerate(brands):
                with cols[i % cols_per_row]:
                    ss_brand = brand.replace(' ', '_').replace('-', '_')
                    key = f"ms_feeds_{key_prefix}_{ss_brand}"
                    st.number_input(brand, min_value=0, step=1, key=key)

        feed_section("HOGS (50 kg)", "hogs_50_kg", ["ULTRAPAK", "PILMICO", "PIGROLAC", "UNIFEEDS", "CJ", "UNO", "PROMIX", "FEED EXPRESS", "VIEPRO", "VAST", "SUNJIN", "KARGADO", "HARVESTA", "NEW HOPE", "OTHERS"], 3)
        feed_section("GAMEFOWL (50 kg)", "gamefowl_50_kg", ["GALLIMAX", "GMP", "INFINITY", "FIREBIRD", "PRO-BOOST", "AVES", "GF", "OTHERS"], 4)
        feed_section("LAYER (50 kg)", "layer_50_kg", ["LAYEX", "PILMICO EXPRESS", "SARIMANOK", "UNIFEEDS", "UNO", "SUNJIN", "LAYENA", "GREENHILLS", "OTHERS"], 3)
        feed_section("GAMEFOWL (1X24 pack)", "gamefowl_ix24_pack", ["THUNDERBIRD", "SALTO", "SAGUPAAN", "WARHAWK", "OTHERS"], 5)
        feed_section("BROILER (50 kg)", "broiler_50_kg", ["PILMICO", "GREENHILLS", "GMC", "UNIFEEDS", "OTHERS"], 5)

    with tab3:
        st.subheader("🐾 Petfood Survey")
        st.caption("Enter number of units sold per month")
        
        col_dog, col_maint, col_cat = st.columns(3)
        with col_dog:
            st.markdown("**DOGFOOD - PUPPY**")
            for brand in ["PEDIGREE", "TOP BREED", "BEEF PRO", "BUDDY'S CHOMP", "DERBY", "YUM YUM", "DOGGY WOGGY", "VITALITY", "ROYAL CANIN", "BOW WOW", "WOOFY", "SPECIAL DOG", "OTHERS"]:
                key = f'ms_pet_dog_pup_{brand.replace(" ", "_")}' 
                st.number_input(brand, min_value=0, step=1, key=key)
            
        with col_maint:   
            st.markdown("**DOGFOOD - MAINTENANCE**")
            for brand in ["PEDIGREE", "TOP BREED", "BEEF PRO", "BUDDY'S CHOMP", "DERBY", "YUM YUM", "DOGGY WOGGY", "VITALITY", "ROYAL CANIN", "BOW WOW", "WOOFY", "SPECIAL DOG", "OTHERS"]:
                key = f"ms_pet_dog_maint_{brand.replace(' ', '_')}"
                st.number_input(brand, min_value=0, step=1, key=key)
                
        with col_cat:
            st.markdown("**CATFOOD**")
            for brand in ["TOP CAT", "WHISKAS", "DIXIE", "SPECIAL CAT", "AOZI", "ROYAL CANIN", "OTHERS"]:
                key = f"ms_pet_cat_{brand.replace(' ', '_')}"
                st.number_input(brand, min_value=0, step=1, key=key)

    with tab4:
        st.subheader("💊 VETMED Survey")
        st.caption("Indicate amount of purchase per month")
        
        for brand in ["UNIVET", "EXCELLENCE", "LDI", "SAGUPAAN", "BATTLECOCK", "TRYCO", "OTHERS"]:
            st.markdown(f"**{brand}**")
            cols = st.columns(4)
            for i, cat in enumerate(["WSP", "INJECTABLE", "DISINFECTANT", "GAMEFOWL_PREP"]):
                with cols[i]:
                    key = f"ms_vet_{brand.replace(' ', '_')}_{cat.replace(' ', '_')}"
                    st.number_input(cat, min_value=0, step=1, key=key, label_visibility="visible")
            st.divider()

    with tab5:
        st.subheader("✅ Review & Submit")

        store_name = str(st.session_state.get("ms_store_name", "")).strip().upper()
        owner_name = str(st.session_state.get("ms_owner_name", "")).strip().upper()
        street = str(st.session_state.get("ms_street", "")).strip().upper()
        barangay = str(st.session_state.get("ms_barangay", "")).strip().upper()
        city = str(st.session_state.get("ms_city", "")).strip().upper()
        province = str(st.session_state.get("ms_province", "")).strip().upper()
        contact_no = str(st.session_state.get("ms_contact", "")).strip()
        
        bday_val = st.session_state.get("ms_bday")
        owner_bday = bday_val.strftime("%Y-%m-%d") if bday_val and isinstance(bday_val, date) else ""

        payload = {
            "timestamp": datetime.now(PHT).strftime("%Y-%m-%d %H:%M:%S"),
            "username": user.get("username", ""),
            "branch": user.get("branch", ""),
            "store_name": store_name,
            "owner_name": owner_name,
            "street": street,
            "barangay": barangay,
            "city": city,
            "province": province,
            "contact_no": contact_no,
            "owner_bday": owner_bday,
            "class_a": int(st.session_state.get("ms_class_a", 0)),
            "class_b": int(st.session_state.get("ms_class_b", 0)),
            "class_c": int(st.session_state.get("ms_class_c", 0)),
            "distribution": str(st.session_state.get("ms_dist_type", "")).strip(),
        }

        sub_dealers = st.session_state.get("ms_direct_dealers", [])
        payload["sub_dealer_count"] = len(sub_dealers)
        for i in range(1, 11):
            payload[f"sub_dealer_{i}"] = sub_dealers[i-1] if i <= len(sub_dealers) else ""

        def process_feeds(prefix, brands):
            for brand in brands:
                ss_brand = brand.replace(' ', '_').replace('-', '_')
                key = f"ms_feeds_{prefix}_{ss_brand}"
                
                if brand == "ULTRAPAK":
                    payload_brand = "ULTAPAK"
                elif brand == "FEED EXPRESS":
                    payload_brand = "FEED_EXPRESS"
                elif brand == "PILMICO EXPRESS":
                    payload_brand = "PILMICO_EXPRESS"
                elif brand == "PRO-BOOST":
                    payload_brand = "PRO-BOOST"
                else:
                    payload_brand = brand.replace(' ', '_')
                
                payload[f"feeds_{prefix}_{payload_brand}"] = int(st.session_state.get(key, 0))

        process_feeds("hogs_50_kg", ["ULTRAPAK", "PILMICO", "PIGROLAC", "UNIFEEDS", "CJ", "UNO", "PROMIX", "FEED EXPRESS", "VIEPRO", "VAST", "SUNJIN", "KARGADO", "HARVESTA", "NEW HOPE", "OTHERS"])
        process_feeds("gamefowl_50_kg", ["GALLIMAX", "GMP", "INFINITY", "FIREBIRD", "PRO-BOOST", "AVES", "GF", "OTHERS"])
        process_feeds("layer_50_kg", ["LAYEX", "PILMICO EXPRESS", "SARIMANOK", "UNIFEEDS", "UNO", "SUNJIN", "LAYENA", "GREENHILLS", "OTHERS"])
        process_feeds("gamefowl_ix24_pack", ["THUNDERBIRD", "SALTO", "SAGUPAAN", "WARHAWK", "OTHERS"])
        process_feeds("broiler_50_kg", ["PILMICO", "GREENHILLS", "GMC", "UNIFEEDS", "OTHERS"])

        for brand in ["PEDIGREE", "TOP BREED", "BEEF PRO", "BUDDY'S CHOMP", "DERBY", "YUM YUM", "DOGGY WOGGY", "VITALITY", "ROYAL CANIN", "BOW WOW", "WOOFY", "SPECIAL DOG", "OTHERS"]:
            safe = brand.replace(' ', '_')
            payload[f"pet_dog_pup_{safe}"] = int(st.session_state.get(f"ms_pet_dog_pup_{safe}", 0))
            payload[f"pet_dog_maint_{safe}"] = int(st.session_state.get(f"ms_pet_dog_maint_{safe}", 0))

        for brand in ["TOP CAT", "WHISKAS", "DIXIE", "SPECIAL CAT", "AOZI", "ROYAL CANIN", "OTHERS"]:
            safe = brand.replace(' ', '_')
            payload[f"pet_cat_{safe}"] = int(st.session_state.get(f"ms_pet_cat_{safe}", 0))

        for brand in ["UNIVET", "EXCELLENCE", "LDI", "SAGUPAAN", "BATTLECOCK", "TRYCO", "OTHERS"]:
            for cat in ["WSP", "INJECTABLE", "DISINFECTANT", "GAMEFOWL_PREP"]:
                safe_brand = brand.replace(' ', '_')
                safe_cat = cat.replace(' ', '_')
                key = f"ms_vet_{safe_brand}_{safe_cat}"
                payload[f"vet_{safe_brand}_{safe_cat}"] = int(st.session_state.get(key, 0))

        if st.button("💾 Save to Google Sheets", type="primary", use_container_width=True):
            st.session_state.ms_attempted_submit = True
            
            with st.spinner("Saving..."):
                user_branch = user.get("branch", "")
                success = append_to_sheet(user_branch, payload)
                
                if success:
                    st.session_state.ms_save_success = True
                    
                    for k in list(st.session_state.keys()):
                        if k.startswith("ms_") and k != "ms_save_success":
                            del st.session_state[k]
                    
                    st.rerun()
                else:
                    st.error("❌ Failed to save.")

        if st.session_state.get("ms_save_success", False):
            st.success("🎉 Data saved successfully! Form has been reset.")
            if st.button("➕ Submit Another Entry"):
                st.session_state.ms_save_success = False
                st.session_state.ms_attempted_submit = False
                st.rerun()
        else:
            if st.session_state.get("ms_attempted_submit", False):
                errors = []
                if not store_name: 
                    errors.append("Store Name is required")
                if not owner_name: 
                    errors.append("Owner's Name is required")
                if not barangay:
                    errors.append("Barangay is required")
                if not city:
                    errors.append("City is required")
                if not province:
                    errors.append("Province is required")
                if not contact_no:
                    errors.append("Contact Number is required")
                else:
                    import re
                    contact_clean = contact_no.replace(" ", "").replace("-", "")
                    if not re.match(r"^09\d{9}$", contact_clean):
                        errors.append("Please enter a valid Philippine mobile number")
    
                # ✅ Validate that only ONE class is selected
                class_a_val = int(st.session_state.get("ms_class_a", 0))
                class_b_val = int(st.session_state.get("ms_class_b", 0))
                class_c_val = int(st.session_state.get("ms_class_c", 0))
                
                classes_with_values = sum([
                    1 if class_a_val > 0 else 0,
                    1 if class_b_val > 0 else 0,
                    1 if class_c_val > 0 else 0
                ])
                
                if classes_with_values == 0:
                    errors.append("Please select at least one Store Class (A, B, or C)")
                elif classes_with_values > 1:
                    errors.append("Please select only ONE Store Class per store (not multiple classes)")
    
                if errors:
                    for e in errors: 
                        st.error(f"❌ {e}")
                else:
                    st.success("✅ All required fields completed.")
            else:
                st.info("📝 Please fill in all required fields (marked with *) and click Save.")
