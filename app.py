import streamlit as st
import pandas as pd
import plotly.express as px

st.write("XSRF Protection is currently:", st.get_option("server.enableXsrfProtection"))

# --- PAGE CONFIG ---
st.set_page_config(page_title="Retail Sales Intelligence", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e6e9ef; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Retail Sales Intelligence App")

# --- SIDEBAR: DATA INTEGRATION ---
st.sidebar.header("Data Integration")
sales_file = st.sidebar.file_uploader("Upload Weekly Sales", type=['xlsx'])
stores_file = st.sidebar.file_uploader("Upload Store Master", type=['xlsx'])

# Add a fallback for the network error
use_default = st.sidebar.checkbox("Use default data (Check this if upload fails with AxiosError)")

if use_default:
    # Read the files directly from the GitHub repository
    sales_df = pd.read_excel("data/retail_weekly_sales.xlsx")
    stores_df = pd.read_excel("data/store_master.xlsx")
    st.success("Default data loaded successfully!")
    
elif sales_file and stores_file:
    # Read the uploaded files
    sales_df = pd.read_excel(sales_file)
    stores_df = pd.read_excel(stores_file)
    st.success("Files uploaded successfully!")
else:
    st.warning("Please upload data or check the 'Use default data' box to proceed.")
    st.stop() # Stops the rest of the app from crashing while waiting for data

@st.cache_data
def load_and_process_data(s_file, m_file):
    try:
        # Load datasets
        df_sales = pd.read_excel(s_file)
        df_master = pd.read_excel(m_file)

        # 1. Clean redundant columns from Sales before merge
        redundant_cols = ['store_name', 'region', 'city', 'store_format']
        cols_to_drop = [col for col in redundant_cols if col in df_sales.columns]
        df_sales_cleaned = df_sales.drop(columns=cols_to_drop)

        # 2. Merge on store_id
        merged_df = pd.merge(df_sales_cleaned, df_master, on='store_id', how='left')

        # 3. Robust Date Parsing
        if 'week_start_date' in merged_df.columns:
            merged_df['week_start_date'] = pd.to_datetime(merged_df['week_start_date'], errors='coerce')
            merged_df = merged_df.dropna(subset=['week_start_date'])
            merged_df['week_start_date'] = merged_df['week_start_date'].dt.date

        # 4. Numeric Sanitization (Crucial Fix for TypeError)
        # This forces strings to NaN, then fills NaN with 0 so math operations work
        numeric_cols = [
            'gross_sales', 'net_sales', 'discount_amount', 
            'returns_amount', 'sales_target', 'transactions', 
            'units_sold', 'inventory_on_hand'
        ]
        
        for col in numeric_cols:
            if col in merged_df.columns:
                merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce').fillna(0)

        return merged_df

    except Exception as e:
        st.error(f"Error processing files: {e}")
        return None

if sales_file and master_file:
    df = load_and_process_data(sales_file, master_file)

    if df is not None and not df.empty:
        # --- SIDEBAR: FILTERS ---
        st.sidebar.header("Global Filters")
        
        unique_weeks = sorted(df['week_start_date'].unique())
        
        f_week = st.sidebar.multiselect("Week Start Date", options=unique_weeks, default=unique_weeks)
        f_region = st.sidebar.multiselect("Region", options=df['region'].unique(), default=df['region'].unique())
        f_format = st.sidebar.multiselect("Store Format", options=df['store_format'].unique(), default=df['store_format'].unique())
        f_cat = st.sidebar.multiselect("Product Category", options=df['product_category'].unique(), default=df['product_category'].unique())
        f_city = st.sidebar.multiselect("City", options=df['city'].unique(), default=df['city'].unique())
        f_store = st.sidebar.multiselect("Store Name", options=df['store_name'].unique(), default=df['store_name'].unique())

        # Apply Filters
        mask = (
            df['week_start_date'].isin(f_week) & 
            df['region'].isin(f_region) & 
            df['store_format'].isin(f_format) & 
            df['product_category'].isin(f_cat) &
            df['city'].isin(f_city) &
            df['store_name'].isin(f_store)
        )
        filtered_df = df[mask]

        if filtered_df.empty:
            st.warning("No data matches the current filter selection.")
        else:
            # --- KPI CALCULATIONS ---
            # All values are now guaranteed floats/ints thanks to the sanitization step
            total_net_sales = filtered_df['net_sales'].sum()
            total_target = filtered_df['sales_target'].sum()
            total_trans = filtered_df['transactions'].sum()
            total_returns = filtered_df['returns_amount'].sum()
            total_discount = filtered_df['discount_amount'].sum()
            total_gross = filtered_df['gross_sales'].sum()

            target_ach = (total_net_sales / total_target * 100) if total_target > 0 else 0
            atv = (total_net_sales / total_trans) if total_trans > 0 else 0
            return_rate = (total_returns / total_net_sales * 100) if total_net_sales > 0 else 0
            disc_rate = (total_discount / total_gross * 100) if total_gross > 0 else 0

            # --- KPI ROW ---
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Net Sales", f"${total_net_sales:,.0f}")
            k2.metric("Target Achievement", f"{target_ach:.1f}%", delta=f"{target_ach-100:.1f}%")
            k3.metric("Avg Trans. Value", f"${atv:.2f}")
            k4.metric("Return Rate", f"{return_rate:.1f}%", delta_color="inverse")
            k5.metric("Discount Rate", f"{disc_rate:.1f}%")

            st.markdown("---")

            # --- CHARTS ---
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("Weekly Sales Trend")
                trend = filtered_df.groupby('week_start_date')['net_sales'].sum().reset_index()
                fig_trend = px.line(trend, x='week_start_date', y='net_sales', markers=True, template="plotly_white")
                st.plotly_chart(fig_trend, use_container_width=True)

            with c2:
                st.subheader("Sales by Region")
                reg_chart = filtered_df.groupby('region')['net_sales'].sum().reset_index()
                fig_reg = px.pie(reg_chart, values='net_sales', names='region', hole=0.4)
                st.plotly_chart(fig_reg, use_container_width=True)

            c3, c4 = st.columns(2)

            with c3:
                st.subheader("Category Performance")
                cat_perf = filtered_df.groupby('product_category')['net_sales'].sum().sort_values().reset_index()
                fig_cat = px.bar(cat_perf, x='net_sales', y='product_category', orientation='h', color='net_sales')
                st.plotly_chart(fig_cat, use_container_width=True)

            with c4:
                st.subheader("Top 10 Stores by Sales")
                top_stores = filtered_df.groupby('store_name')['net_sales'].sum().nlargest(10).reset_index()
                fig_store = px.bar(top_stores, x='net_sales', y='store_name', orientation='h', color_discrete_sequence=['#00CC96'])
                st.plotly_chart(fig_store, use_container_width=True)

            st.subheader("Stockout Risk Analysis")
            fig_stock = px.scatter(
                filtered_df, 
                x='units_sold', 
                y='inventory_on_hand', 
                size='net_sales', 
                color='product_category',
                hover_name='store_name',
                labels={'units_sold': 'Sales Velocity (Units Sold)', 'inventory_on_hand': 'Inventory On Hand'},
                title="Inventory Levels vs. Sales Velocity"
            )
            st.plotly_chart(fig_stock, use_container_width=True)

            # --- BUSINESS INSIGHTS ---
            st.markdown("---")
            st.subheader("💡 Automated Business Insights")
            
            i1, i2 = st.columns(2)
            
            with i1:
                reg_totals = filtered_df.groupby('region')['net_sales'].sum()
                st.info(f"🏆 **Top Region:** {reg_totals.idxmax()} (${reg_totals.max():,.0f})")
                st.warning(f"📉 **Weakest Region:** {reg_totals.idxmin()} (${reg_totals.min():,.0f})")
                
                # Stores missing target
                st_targets = filtered_df.groupby('store_name')[['net_sales', 'sales_target']].sum()
                missed = st_targets[st_targets['net_sales'] < st_targets['sales_target']].index.tolist()
                if missed:
                    st.error(f"🚩 **Alert:** {len(missed)} stores are currently below their revenue targets.")

            with i2:
                # Calculate return rates per category
                ret_cat = filtered_df.groupby('product_category').apply(lambda x: (x['returns_amount'].sum() / x['net_sales'].sum() * 100) if x['net_sales'].sum() > 0 else 0).sort_values(ascending=False)
                st.markdown("**Top 3 Categories with Highest Return Rates:**")
                for cat, val in ret_cat.head(3).items():
                    st.write(f"- {cat}: {val:.2f}%")

            # --- EXPORT ---
            st.markdown("---")
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Filtered Data (CSV)", data=csv, file_name='retail_intelligence_report.csv', mime='text/csv')

else:
    st.info("👋 Welcome! Please upload 'retail_weekly_sales.xlsx' and 'store_master.xlsx' in the sidebar to visualize your retail data.")
