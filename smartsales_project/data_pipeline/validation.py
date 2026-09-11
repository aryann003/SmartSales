import pandas as pd


def validate_data(df):

    error = []

    if df['unit_price'].min() < 0:
        error.append("Found unit_price <= 0 after cleaning")

    if df['order_date'].isnull().sum() > 0:
        error.append("Found rows with missing order_date")

    if df['customer_ref'].isnull().sum() > 0:
        error.append("Found rows with missing customer_ref")

    if df['quantity'].isnull().sum() > 0:
        error.append("Found rows with missing quantity")

    if df.duplicated().sum() > 0:
        error.append(f"found {df.duplicated().sum()} duplicate rows after cleaning")

    if error:
        print("VALIDATION FAILED:")

        for e in error:
            print(f" - {e}")
        raise ValueError("Data validation failed")

    print("Data validation passed: no issues found")

    return df


if __name__ == '__main__':
    from ingestion import load_raw_data
    from cleaning import clean_data

    df = load_raw_data()
    df = clean_data(df)
    df = validate_data(df)


    print("\nFinal dataset ready for loading:")
    print(df.describe(include='all').iloc[:, :5])