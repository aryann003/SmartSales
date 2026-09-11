import pandas as pd


def clean_data(df):
    """Apply all cleaning rules identified during Day 8 exploration."""

    initial_count = len(df)

    # 1. Drop rows with missing Customer ID — can't attribute revenue to no one
    df = df.dropna(subset=['Customer ID'])

    # 2. Drop rows with missing Description
    df = df.dropna(subset=['Description'])

    # 3. Remove exact duplicate rows
    df = df.drop_duplicates()

    # 4. Convert InvoiceDate from string to real datetime
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], errors='coerce')
    df = df.dropna(subset=['InvoiceDate'])

    # 5. Flag returns: negative quantity OR invoice starts with 'C'
    df['is_return'] = (df['Quantity'] < 0) | (df['Invoice'].astype(str).str.startswith('C'))

    # 6. Drop rows with invalid prices (zero or negative) — bad data either way
    df = df[df['Price'] > 0]

    # 7. Clean up messy text in Description (extra whitespace, consistent casing)
    df['Description'] = df['Description'].astype(str).str.strip().str.title()

    # 8. Derived field: revenue = Quantity x Price
    #    (for returns, this will naturally be negative, which is correct)
    df['revenue'] = df['Quantity'] * df['Price']

    # 9. Standardize column names to match our Django models
    df = df.rename(columns={
        'Invoice': 'order_ref',
        'StockCode': 'product_code',
        'Description': 'product_name',
        'Quantity': 'quantity',
        'InvoiceDate': 'order_date',
        'Price': 'unit_price',
        'Customer ID': 'customer_ref',
        'Country': 'country',
    })

    final_count = len(df)
    print(f"Cleaning complete: {initial_count} raw rows -> {final_count} clean rows "
          f"({initial_count - final_count} removed)")

    return df


if __name__ == '__main__':
    from ingestion import load_raw_data

    df_raw = load_raw_data()
    df_clean = clean_data(df_raw)

    print("\nCleaned columns:", list(df_clean.columns))
    print("\nSample of cleaned data:")
    print(df_clean.head())
    print("\nReturn rows:", df_clean['is_return'].sum())
    print("Sale rows:", (~df_clean['is_return']).sum())