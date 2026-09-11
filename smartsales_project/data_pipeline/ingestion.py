import pandas as pd

def load_raw_data(filepath='data/online_retail_II.csv'):
    df = pd.read_csv(filepath)

    print(f"Loaded {len(df)} raw rows from {filepath}")
    return df


if __name__ == '__main__':
    df = load_raw_data()
    print(df.head())

