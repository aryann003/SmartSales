import logging

import pandas as pd

logger = logging.getLogger("smartsales.pipeline")

DEFAULT_PATH = "data/online_retail_II.csv"


def load_raw_data(filepath=DEFAULT_PATH, limit=None):
    """Read the raw Online Retail II CSV. ``limit`` keeps only the first N rows."""
    df = pd.read_csv(filepath, nrows=limit)
    logger.info("Loaded %d raw rows from %s", len(df), filepath)
    return df
