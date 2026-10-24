import logging

logger = logging.getLogger("smartsales.pipeline")

REQUIRED_COLUMNS = ["order_ref", "product_code", "product_name", "quantity", "order_date",
                    "unit_price", "customer_ref", "country", "is_return", "revenue"]


class DataValidationError(ValueError):
    """Raised when cleaned data fails a validation gate. ``issues`` lists every problem."""

    def __init__(self, issues):
        self.issues = issues
        super().__init__("Data validation failed: " + "; ".join(issues))


def find_issues(df):
    """Return a list of human-readable problems (empty if the data is loadable)."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [f"Missing columns: {', '.join(missing)}"]

    issues = []
    if df.empty:
        issues.append("No rows left after cleaning")
    if (df["unit_price"] <= 0).any():
        issues.append("Found unit_price <= 0 after cleaning")
    for column in ("order_date", "customer_ref", "quantity"):
        count = int(df[column].isnull().sum())
        if count:
            issues.append(f"Found {count} rows with missing {column}")
    duplicates = int(df.duplicated().sum())
    if duplicates:
        issues.append(f"Found {duplicates} duplicate rows after cleaning")
    return issues


def validate_data(df):
    """Validation gate: halt the load (nothing is written) if any check fails."""
    issues = find_issues(df)
    if issues:
        for issue in issues:
            logger.error("Validation: %s", issue)
        raise DataValidationError(issues)
    logger.info("Data validation passed")
    return df
