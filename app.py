import streamlit as st
import pandas as pd
import re

# 1. Page Configuration & Title
st.set_page_config(page_title="Cai Lab Inventory", page_icon="🧪", layout="wide")
st.title("🧪 Purdue Cai Lab Chemical Inventory")
st.write("Welcome to the Cai Lab Chemical Inventory Lookup System!")

# 2. Connect to your Google Sheet
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS3WZrrHHeezIXGFn6n5lyvy99mV6i_D8vp8BNIfHK3kfVZY_7VqydklCnlfSMYeXYWuIO_taypSihh/pub?gid=752284712&single=true&output=csv"

# Robust text cleaning function to eliminate spacing, punctuation, and case discrepancies
def clean_text_flexible(text):
    if pd.isna(text):
        return ""
    text = str(text).upper()
    cleaned = re.sub(r'[^A-Z0-9]', '', text)
    return cleaned

# Smart function to join Location and Sub-Location elegantly without leaving empty parentheses
def combine_location(row):
    loc = str(row['Location']).strip()
    sub_loc = str(row['Cleaned_Sub_Location']).strip()
    # If sub_location is empty or NaN, just return the main location
    if not sub_loc or sub_loc.upper() == 'NAN' or sub_loc == '':
        return loc
    return f"{loc} ({sub_loc})"

@st.cache_data(ttl=60) # Auto-refresh data every 60 seconds
def load_and_calculate_inventory():
    df = pd.read_csv(GOOGLE_SHEET_URL)
    
    # --- FLEXIBLE COLUMN MAPPING (Anti-structural change) ---
    # Dynamically find columns by matching keywords instead of strict alignment
    col_mapping = {}
    for col in df.columns:
        col_lower = str(col).lower()
        if 'timestamp' in col_lower:
            col_mapping['Timestamp'] = col
        elif 'action' in col_lower:
            col_mapping['Action'] = col
        elif 'name' in col_lower:
            col_mapping['Name'] = col
        elif 'cas' in col_lower:
            col_mapping['CAS'] = col
        elif 'size' in col_lower or 'package' in col_lower:
            col_mapping['Size'] = col
        elif 'location' in col_lower and 'sub' not in col_lower and 'description' not in col_lower and 'shelf' not in col_lower:
            col_mapping['Location'] = col
        elif 'sub' in col_lower or 'shelf' in col_lower or 'bin' in col_lower or 'description' in col_lower:
            col_mapping['Sub_Location'] = col
        elif 'qty' in col_lower or 'quantity' in col_lower or 'column 8' in col_lower:
            # Fallback to map "Column 8" if data filled there
            if 'Quantity' not in col_mapping or 'column 8' in col_lower:
                col_mapping['Quantity'] = col

    # Build optimized internal dataframe
    processed_df = pd.DataFrame()
    processed_df['Timestamp'] = df[col_mapping.get('Timestamp', df.columns[0])]
    processed_df['Action'] = df[col_mapping.get('Action', df.columns[1])]
    processed_df['Name'] = df[col_mapping.get('Name', df.columns[2])]
    processed_df['CAS'] = df[col_mapping.get('CAS', df.columns[3])]
    processed_df['Size'] = df[col_mapping.get('Size', df.columns[4])]
    processed_df['Location'] = df[col_mapping.get('Location', df.columns[5])]
    processed_df['Sub_Location'] = df[col_mapping.get('Sub_Location', df.columns[6])]
    
    # Smart fallback for Quantity: if real Quantity column is empty, check Column 8
    real_qty_col = col_mapping.get('Quantity', df.columns[7])
    processed_df['Quantity'] = pd.to_numeric(df[real_qty_col], errors='coerce').fillna(0)
    if processed_df['Quantity'].sum() == 0 and 'Column 8' in df.columns:
        processed_df['Quantity'] = pd.to_numeric(df['Column 8'], errors='coerce').fillna(0)

    # Standardize data fields
    processed_df['Cleaned_CAS'] = processed_df['CAS'].astype(str).str.strip()
    processed_df['Cleaned_Size'] = processed_df['Size'].apply(clean_text_flexible)
    processed_df['Cleaned_Sub_Location'] = processed_df['Sub_Location'].apply(clean_text_flexible)
    
    # Use the optimized function to prevent system-generated trailing parentheses
    processed_df['Full_Location_Standardized'] = processed_df.apply(combine_location, axis=1)
    
    processed_df['Name'] = processed_df['Name'].astype(str).str.strip()
    
    # Inventory calculation logic
    processed_df['Adjusted_Qty'] = processed_df.apply(
        lambda row: -row['Quantity'] if 'Check-out' in str(row['Action']) else row['Quantity'], 
        axis=1
    )
    
    processed_df = processed_df.sort_values('Timestamp')
    qty_series = processed_df.groupby(['Cleaned_CAS', 'Cleaned_Size', 'Full_Location_Standardized'])['Adjusted_Qty'].sum()
    name_mapping = processed_df.groupby('Cleaned_CAS')['Name'].last()
    
    inventory = qty_series.reset_index()
    inventory['Chemical Name'] = inventory['Cleaned_CAS'].map(name_mapping)
    
    inventory = inventory[['Chemical Name', 'Cleaned_CAS', 'Cleaned_Size', 'Full_Location_Standardized', 'Adjusted_Qty']]
    inventory.columns = ['Chemical Name', 'CAS Number', 'Size', 'Location', 'Quantity Left']
    inventory = inventory[pd.to_numeric(inventory['Quantity Left']) > 0]
    
    return inventory.astype(str)

try:
    df_inventory = load_and_calculate_inventory()

    # 3. Universal Search Bar
    search_query = st.text_input("🔍 Search by any keyword (Chemical Name, CAS, Location, Size, etc.):", "")

    if search_query:
        cleaned_query = clean_text_flexible(search_query)
        mask = df_inventory.apply(
            lambda row: row.str.contains(search_query, case=False).any() or 
                        row.apply(clean_text_flexible).str.contains(cleaned_query, case=False).any(), 
            axis=1
        )
        result = df_inventory[mask]
    else:
        result = df_inventory

    # 4. Display Results Table
    st.subheader(f"📊 Available Chemicals in Stock: {len(result)}")
    st.dataframe(result, use_container_width=True)

except Exception as e:
    st.error("Waiting for the first data entry, or please verify that the Google Sheet URL is properly configured.")
