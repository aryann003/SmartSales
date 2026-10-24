import io
from unittest import mock

import pandas as pd
import pytest
from django.core.management import CommandError, call_command

from customers.models import Customer
from data_pipeline.cleaning import clean_data
from data_pipeline.ingestion import load_raw_data
from data_pipeline.loader import AlreadyLoadedError, load_data, run_pipeline
from data_pipeline.validation import DataValidationError, find_issues, validate_data
from orders.models import Order, OrderItem, Return
from products.models import Product

COLUMNS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
ROWS = [
    # good rows (two lines on invoice 10001)
    ["10001", "A1", "white mug", 2, "2026-06-01 10:00", 5.0, 12345.0, "India"],
    ["10001", "B2", "red lamp", 1, "2026-06-01 10:00", 20.0, 12345.0, "India"],
    ["10002", "A1", "white mug", 3, "2026-06-02 09:00", 5.0, 67890.0, "UK"],
    ["C10003", "A1", "white mug", -1, "2026-06-03 11:00", 5.0, 12345.0, "India"],  # return
    # bad rows, each should be dropped by a cleaning rule
    ["10004", "B2", "red lamp", 1, "2026-06-04 10:00", 20.0, None, "India"],  # no customer
    ["10005", "C3", None, 1, "2026-06-04 10:00", 3.0, 12345.0, "India"],  # no description
    ["10001", "A1", "white mug", 2, "2026-06-01 10:00", 5.0, 12345.0, "India"],  # exact duplicate
    ["10006", "D4", "free item", 1, "2026-06-05 10:00", 0.0, 12345.0, "India"],  # zero price
    ["10007", "A1", "white mug", 1, "not-a-date", 5.0, 12345.0, "India"],  # bad date
]


def raw_df():
    return pd.DataFrame(ROWS, columns=COLUMNS)


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "retail.csv"
    raw_df().to_csv(path, index=False)
    return str(path)


class TestCleaning:
    def test_bad_rows_are_removed(self):
        clean = clean_data(raw_df())
        assert len(clean) == 4
        assert set(clean["order_ref"]) == {"10001", "10002", "C10003"}

    def test_columns_are_renamed_for_the_models(self):
        clean = clean_data(raw_df())
        assert {"order_ref", "product_code", "product_name", "quantity", "order_date",
                "unit_price", "customer_ref", "country", "is_return", "revenue"} <= set(clean.columns)

    def test_returns_are_flagged_and_have_negative_revenue(self):
        clean = clean_data(raw_df()).set_index("order_ref")
        assert bool(clean.loc["C10003", "is_return"]) is True
        assert clean.loc["C10003", "revenue"] == -5.0
        assert not clean.loc["10002", "is_return"]

    def test_descriptions_are_normalised(self):
        assert set(clean_data(raw_df())["product_name"]) == {"White Mug", "Red Lamp"}

    def test_input_is_not_mutated(self):
        df = raw_df()
        before = df.copy()
        clean_data(df)
        pd.testing.assert_frame_equal(df, before)

    def test_negative_quantity_without_c_prefix_is_a_return(self):
        df = raw_df().iloc[[0]].copy()
        df["Quantity"] = -3
        assert bool(clean_data(df)["is_return"].iloc[0]) is True


class TestValidation:
    def test_clean_data_passes(self):
        assert find_issues(clean_data(raw_df())) == []
        validate_data(clean_data(raw_df()))

    def test_raw_data_fails_loudly_with_every_issue_listed(self):
        renamed = raw_df().rename(columns={"Invoice": "order_ref"})
        assert "Missing columns" in find_issues(renamed)[0]

    def test_detects_price_problems(self):
        df = clean_data(raw_df())
        df.loc[df.index[0], "unit_price"] = 0
        assert "unit_price <= 0" in " ".join(find_issues(df))

    def test_detects_missing_values_and_duplicates(self):
        df = clean_data(raw_df())
        df.loc[df.index[0], "customer_ref"] = None
        df = pd.concat([df, df.iloc[[1]]])
        issues = " ".join(find_issues(df))
        assert "missing customer_ref" in issues and "duplicate" in issues

    def test_empty_data_is_invalid(self):
        assert "No rows" in find_issues(clean_data(raw_df()).iloc[0:0])[0]

    def test_gate_raises_with_issue_list(self):
        df = clean_data(raw_df())
        df.loc[df.index[0], "unit_price"] = -1
        with pytest.raises(DataValidationError) as exc:
            validate_data(df)
        assert exc.value.issues and "validation failed" in str(exc.value).lower()


@pytest.mark.django_db
class TestLoader:
    def test_loads_every_table_with_correct_counts(self):
        stats = load_data(validate_data(clean_data(raw_df())))
        assert stats == {"customers": 2, "products": 2, "orders": 3, "order_items": 3, "returns": 1}
        assert (Customer.objects.count(), Product.objects.count(), Order.objects.count(),
                OrderItem.objects.count(), Return.objects.count()) == (2, 2, 3, 3, 1)

    def test_order_totals_come_from_non_return_lines(self):
        load_data(clean_data(raw_df()))
        by_date = {str(o.order_date): float(o.total_amount) for o in Order.objects.all()}
        assert by_date == {"2026-06-01": 30.0, "2026-06-02": 15.0, "2026-06-03": 0.0}

    def test_returns_are_stored_with_positive_quantity(self):
        load_data(clean_data(raw_df()))
        assert Return.objects.get().quantity == 1

    def test_reloading_is_refused_so_data_is_never_duplicated(self):
        load_data(clean_data(raw_df()))
        with pytest.raises(AlreadyLoadedError):
            load_data(clean_data(raw_df()))
        assert Order.objects.count() == 3

    def test_replace_reloads_from_scratch(self):
        load_data(clean_data(raw_df()))
        load_data(clean_data(raw_df()), replace=True)
        assert Order.objects.count() == 3 and Customer.objects.count() == 2

    def test_load_is_all_or_nothing(self):
        """A failure part-way must leave no half-loaded data behind."""
        with mock.patch.object(Return.objects, "bulk_create", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                load_data(clean_data(raw_df()))
        assert Customer.objects.count() == Product.objects.count() == Order.objects.count() == 0

    def test_loaded_data_feeds_the_analytics_views(self, client_for):
        load_data(clean_data(raw_df()))
        rows = client_for("analyst").get("/api/analytics/revenue/").data
        assert {str(r["sale_date"]): float(r["total_revenue"]) for r in rows} == {"2026-06-01": 30.0, "2026-06-02": 15.0}


@pytest.mark.django_db
class TestRunPipelineAndCommand:
    def test_ingestion_respects_limit(self, csv_path):
        assert len(load_raw_data(csv_path, limit=3)) == 3

    def test_run_pipeline_reports_what_was_dropped(self, csv_path):
        stats = run_pipeline(csv_path)
        assert stats["raw_rows"] == 9 and stats["clean_rows"] == 4 and stats["dropped_rows"] == 5
        assert stats["orders"] == 3

    def test_command_success_message(self, csv_path, capsys):
        call_command("import_retail_data", "--file", csv_path)
        out = capsys.readouterr().out
        assert "9 raw rows" in out and "5 dropped" in out and "3 orders" in out

    def test_command_limit(self, csv_path):
        call_command("import_retail_data", "--file", csv_path, "--limit", "3")
        assert Order.objects.count() == 2

    def test_command_refuses_to_duplicate(self, csv_path):
        call_command("import_retail_data", "--file", csv_path)
        with pytest.raises(CommandError, match="already exist"):
            call_command("import_retail_data", "--file", csv_path)
        call_command("import_retail_data", "--file", csv_path, "--replace")
        assert Order.objects.count() == 3

    def test_command_missing_file(self):
        with pytest.raises(CommandError, match="File not found"):
            call_command("import_retail_data", "--file", "nope.csv")

    def test_validation_failure_loads_nothing(self, tmp_path):
        bad = tmp_path / "bad.csv"
        pd.DataFrame(ROWS[4:6], columns=COLUMNS).to_csv(bad, index=False)  # every row is dropped by cleaning
        with pytest.raises(CommandError, match="nothing was loaded"):
            call_command("import_retail_data", "--file", str(bad))
        assert Order.objects.count() == 0
