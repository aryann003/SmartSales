import pandas as pd

df = pd.read_csv('data/online_retail_II.csv')

print("Shape:", df.shape)
print("\nColumns:", list(df.columns))
print("\nFirst 5 rows:")
print(df.head())
print("\nData types:")
print(df.dtypes)
print("\nMissing values per column:")
print(df.isnull().sum())
print("\nQuantity stats:")
print(df['Quantity'].describe())






import pandas as pd

df = pd.read_csv('data/online_retail_II.csv')

# How many rows look like returns (negative quantity)?
returns = df[df['Quantity'] < 0]
print("Rows with negative quantity (likely returns):", len(returns))

# How many invoices start with 'C' (cancelled)?
cancelled = df[df['Invoice'].astype(str).str.startswith('C')]
print("Rows with Invoice starting with 'C':", len(cancelled))

# Price sanity check
print("\nPrice stats:")
print(df['Price'].describe())
print("Rows with Price <= 0:", (df['Price'] <= 0).sum())

# Exact duplicate rows
print("\nExact duplicate rows:", df.duplicated().sum())