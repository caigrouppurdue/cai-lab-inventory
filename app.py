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
    # Remove all spaces and non-alphanumeric characters
    cleaned = re.sub(r'[^A-Z0-9]', '', text)
    return cleaned

@st.cache_data(ttl=60) # Auto-refresh data every 60 seconds
def load_and_calculate_inventory():
    df = pd.read_csv(GOOGLE_SHEET_URL)
    
    # Map Google Form columns to standard English headers
    # Expected order: Timestamp, Action, Name, CAS, Size, Location, Sub_Location, Quantity
    df.columns = ['Timestamp', 'Action', 'Name', 'CAS', 'Size', 'Location', 'Sub_Location', 'Quantity']
    
    # Standardize CAS, Size, and Sub_Location for foolproof matching
    df['Cleaned_CAS'] = df['CAS'].astype(str).str.strip()
    df['Cleaned_Size'] = df['Size'].apply(clean_text_flexible)
    df['Cleaned_Sub_Location'] = df['Sub_Location'].apply(clean_text_flexible)
    
    # Create standardized full location
    df['Full_Location_Standardized'] = df['Location'].astype(str) + " (" + df['Cleaned_Sub_Location'] + ")"
    
    # Clean up Chemical Name for display (just strip outer spaces)
    df['Name'] = df['Name'].astype(str).str.strip()
    
    # Ensure Quantity is numeric
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
    
    # Inventory Math: Convert 'Check-out' quantities into negative numbers
    df['Adjusted_Qty'] = df.apply(
        lambda row: -row['Quantity'] if 'Check-out' in str(row['Action']) else row['Quantity'], 
        axis=1
    )
    
    # Sort by Timestamp so the most recent entry is at the bottom (for fetching the latest name)
    df = df.sort_values('Timestamp')
    
    # 1. Aggregate quantities grouped ONLY by CAS, Size, and Location (Ignoring Name discrepancies)
    qty_series = df.groupby(['Cleaned_CAS', 'Cleaned_Size', 'Full_Location_Standardized'])['Adjusted_Qty'].sum()
    
    # 2. Fetch the LATEST typed Chemical Name for each unique CAS number to keep display clean
    name_mapping = df.groupby('Cleaned_CAS')['Name'].last()
    
    # 3. Combine them into the final inventory table
    inventory = qty_series.reset_index()
    inventory['Chemical Name'] = inventory['Cleaned_CAS'].map(name_mapping)
    
    # Rearrange and rename columns for display
    inventory = inventory[['Chemical Name', 'Cleaned_CAS', 'Cleaned_Size', 'Full_Location_Standardized', 'Adjusted_Qty']]
    inventory.columns = ['Chemical Name', 'CAS Number', 'Size', 'Location', 'Quantity Left']
    
    # Only display items currently in stock (Quantity > 0)
    inventory = inventory[pd.to_numeric(inventory['Quantity Left']) > 0]
    
    return inventory.astype(str)

try:
    df_inventory = load_and_calculate_inventory()

    # 3. Universal Search Bar
    search_query = st.text_input("🔍 Search by any keyword (Chemical Name, CAS, Location, Size, etc.):", "")

    if search_query:
        # Clean the search query too, just in case someone searches "50 g" or "shelf 2" with erratic spaces
        cleaned_query = clean_text_flexible(search_query)
        
        # Match against either the regular text columns OR the completely compressed strings
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
