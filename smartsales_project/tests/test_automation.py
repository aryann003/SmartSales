import datetime as dt
import json
import time
from unittest import mock

import pytest
import requests
from django.core import mail

from core import automation
from core.models import AutomationLog
from orders.models import Order

SECRET = "s3cret"
URL = "https://n8n.example.com/webhook/new-order"


def ok(code=200):
    return mock.Mock(ok=code < 400, status_code=code)


@pytest.fixture(autouse=True)
def fast_retries(settings):
    settings.WEBHOOK_MAX_ATTEMPTS = 3
    settings.WEBHOOK_BACKOFF_SECONDS = 1.0


class TestSignatures:
    body = b'{"order_id":1}'

    def test_round_trip(self):
        ts = str(int(time.time()))
        assert automation.verify_signature(SECRET, ts, self.body, automation.sign_payload(SECRET, ts, self.body))

    def test_tampered_body_is_rejected(self):
        ts = str(int(time.time()))
        sig = automation.sign_payload(SECRET, ts, self.body)
        assert not automation.verify_signature(SECRET, ts, b'{"order_id":2}', sig)

    def test_wrong_secret_is_rejected(self):
        ts = str(int(time.time()))
        assert not automation.verify_signature("other", ts, self.body, automation.sign_payload(SECRET, ts, self.body))

    def test_replayed_old_request_is_rejected(self):
        ts = str(int(time.time()) - 3600)
        assert not automation.verify_signature(SECRET, ts, self.body, automation.sign_payload(SECRET, ts, self.body))

    @pytest.mark.parametrize("ts,sig", [(None, "x"), ("abc", "x"), ("1", ""), ("1", None)])
    def test_malformed_input_is_rejected(self, ts, sig):
        assert not automation.verify_signature(SECRET, ts, self.body, sig)

    def test_signature_binds_the_timestamp(self):
        sig = automation.sign_payload(SECRET, "1000", self.body)
        assert sig != automation.sign_payload(SECRET, "1001", self.body)


@pytest.mark.django_db
class TestDelivery:
    def test_success_is_signed_and_logged(self):
        with mock.patch("requests.post", return_value=ok()) as post:
            assert automation.deliver_webhook("order.created", {"order_id": 7}, url=URL, secret=SECRET)
        kwargs = post.call_args.kwargs
        headers = kwargs["headers"]
        assert automation.verify_signature(SECRET, headers[automation.TIMESTAMP_HEADER], kwargs["data"],
                                           headers[automation.SIGNATURE_HEADER])
        assert headers[automation.EVENT_HEADER] == "order.created"
        assert json.loads(kwargs["data"]) == {"order_id": 7}
        assert list(AutomationLog.objects.values_list("status", flat=True)) == ["SUCCESS"]

    def test_server_errors_are_retried_with_exponential_backoff(self):
        sleeps = []
        with mock.patch("requests.post", side_effect=[ok(500), ok(503), ok(200)]) as post:
            assert automation.deliver_webhook("e", {}, url=URL, secret=SECRET, sleep=sleeps.append)
        assert post.call_count == 3 and sleeps == [1.0, 2.0]
        assert list(AutomationLog.objects.order_by("id").values_list("status", flat=True)) == ["RETRY", "RETRY", "SUCCESS"]

    def test_network_errors_are_retried(self):
        with mock.patch("requests.post", side_effect=[requests.exceptions.ConnectionError("down"), ok()]):
            assert automation.deliver_webhook("e", {}, url=URL, secret=SECRET, sleep=lambda s: None)
        assert AutomationLog.objects.filter(status="RETRY", message__contains="ConnectionError").exists()

    def test_gives_up_after_max_attempts(self):
        with mock.patch("requests.post", return_value=ok(500)) as post:
            assert not automation.deliver_webhook("e", {}, url=URL, secret=SECRET, sleep=lambda s: None)
        assert post.call_count == 3
        assert list(AutomationLog.objects.order_by("id").values_list("status", flat=True)) == ["RETRY", "RETRY", "FAILED"]

    def test_client_errors_are_not_retried(self):
        with mock.patch("requests.post", return_value=ok(400)) as post:
            assert not automation.deliver_webhook("e", {}, url=URL, secret=SECRET, sleep=lambda s: None)
        assert post.call_count == 1 and AutomationLog.objects.get().status == "FAILED"

    def test_rate_limiting_is_retried(self):
        with mock.patch("requests.post", side_effect=[ok(429), ok()]):
            assert automation.deliver_webhook("e", {}, url=URL, secret=SECRET, sleep=lambda s: None)

    def test_timeout_is_passed_to_requests(self, settings):
        settings.WEBHOOK_TIMEOUT_SECONDS = 2
        with mock.patch("requests.post", return_value=ok()) as post:
            automation.deliver_webhook("e", {}, url=URL, secret=SECRET)
        assert post.call_args.kwargs["timeout"] == 2

    def test_skipped_when_no_url_is_configured(self, settings):
        settings.N8N_WEBHOOK_URL = ""
        with mock.patch("requests.post") as post:
            assert automation.deliver_webhook("e", {}) is False
        post.assert_not_called() and not AutomationLog.objects.exists()


@pytest.mark.django_db
class TestOrderSignal:
    @pytest.fixture
    def configured(self, settings):
        settings.N8N_WEBHOOK_URL = URL
        settings.WEBHOOK_SECRET = SECRET
        settings.WEBHOOK_ASYNC = False

    def test_new_order_sends_one_event_after_commit(self, configured, sample_data, django_capture_on_commit_callbacks):
        with mock.patch("requests.post", return_value=ok()) as post:
            with django_capture_on_commit_callbacks(execute=True):
                order = Order.objects.create(customer=sample_data["asha"], order_date=dt.date(2026, 6, 9), total_amount=15000)
        assert post.call_count == 1
        sent = json.loads(post.call_args.kwargs["data"])
        assert sent["order_id"] == order.id and sent["amount"] == 15000.0 and sent["event"] == "order.created"

    def test_nothing_is_sent_before_the_transaction_commits(self, configured, sample_data):
        with mock.patch("requests.post") as post:
            Order.objects.create(customer=sample_data["asha"], order_date=dt.date(2026, 6, 9), total_amount=5)
        post.assert_not_called()  # still inside the test transaction: callback not run

    def test_updating_an_order_does_not_resend(self, configured, sample_data, django_capture_on_commit_callbacks):
        with mock.patch("requests.post", return_value=ok()) as post:
            with django_capture_on_commit_callbacks(execute=True):
                order = Order.objects.create(customer=sample_data["asha"], order_date=dt.date(2026, 6, 9), total_amount=5)
                order.status = "completed"
                order.save()
        assert post.call_count == 1

    def test_slow_receiver_does_not_block_order_creation(self, configured, settings, sample_data,
                                                         django_capture_on_commit_callbacks):
        """With async delivery, the commit callback only starts a thread."""
        settings.WEBHOOK_ASYNC = True
        with mock.patch("core.automation.threading.Thread") as thread:
            with django_capture_on_commit_callbacks(execute=True):
                Order.objects.create(customer=sample_data["asha"], order_date=dt.date(2026, 6, 9), total_amount=5)
        thread.assert_called_once()
        assert thread.call_args.kwargs["daemon"] is True
        thread.return_value.start.assert_called_once()

    def test_receiver_failure_never_breaks_order_creation(self, configured, sample_data, django_capture_on_commit_callbacks):
        with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")), \
             mock.patch("core.automation.time.sleep"):
            with django_capture_on_commit_callbacks(execute=True):
                order = Order.objects.create(customer=sample_data["asha"], order_date=dt.date(2026, 6, 9), total_amount=5)
        assert Order.objects.filter(id=order.id).exists()
        assert AutomationLog.objects.filter(status="FAILED").exists()


@pytest.mark.django_db
class TestLogEndpoint:
    payload = {"workflow_name": "daily report", "event_type": "run", "status": "SUCCESS", "message": "ok"}

    def test_requires_the_shared_token(self, anon):
        assert anon.post("/api/analytics/log/", self.payload, format="json").status_code == 401
        assert not AutomationLog.objects.exists()

    def test_wrong_token_is_rejected(self, anon):
        resp = anon.post("/api/analytics/log/", self.payload, format="json", HTTP_X_AUTOMATION_TOKEN="wrong")
        assert resp.status_code == 401

    def test_endpoint_is_closed_when_no_key_is_configured(self, anon, settings):
        settings.AUTOMATION_API_KEY = ""
        resp = anon.post("/api/analytics/log/", self.payload, format="json", HTTP_X_AUTOMATION_TOKEN="")
        assert resp.status_code == 401

    def test_valid_token_creates_a_log(self, anon):
        resp = anon.post("/api/analytics/log/", self.payload, format="json", HTTP_X_AUTOMATION_TOKEN="test-automation-key")
        assert resp.status_code == 201 and AutomationLog.objects.get().workflow_name == "daily report"

    def test_invalid_status_is_rejected(self, anon):
        bad = {**self.payload, "status": "WHATEVER"}
        resp = anon.post("/api/analytics/log/", bad, format="json", HTTP_X_AUTOMATION_TOKEN="test-automation-key")
        assert resp.status_code == 400

    def test_missing_fields_are_rejected(self, anon):
        resp = anon.post("/api/analytics/log/", {"status": "SUCCESS"}, format="json", HTTP_X_AUTOMATION_TOKEN="test-automation-key")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestDailyReport:
    HDR = {"HTTP_X_AUTOMATION_TOKEN": "test-automation-key"}

    def test_requires_the_shared_token(self, anon):
        assert anon.post("/api/automation/daily-report/", {}, format="json").status_code == 401

    def test_report_contents(self, anon, sample_data):
        report = anon.post("/api/automation/daily-report/", {"date": "2026-06-03"}, format="json", **self.HDR).data
        assert report["revenue"] == 60.0 and report["orders"] == 1 and report["returns"] == 1
        assert report["change_vs_previous_day_pct"] == 50.0  # 40 -> 60
        assert report["top_products"] == [{"name": "Lamp", "revenue": 60.0}]
        assert report["anomaly"] is False

    def test_defaults_to_the_latest_day_with_orders(self, anon, sample_data):
        report = anon.post("/api/automation/daily-report/", {}, format="json", **self.HDR).data
        assert report["report_date"] == "2026-06-03"

    def test_empty_database(self, anon, db):
        report = anon.post("/api/automation/daily-report/", {}, format="json", **self.HDR).data
        assert report["has_data"] is False

    def test_flags_a_sales_drop(self, anon, sample_data):
        from decimal import Decimal
        from orders.models import OrderItem
        # a huge earlier day makes the last day a >30% drop versus the 7-day average
        big = Order.objects.create(customer=sample_data["asha"], order_date=dt.date(2026, 5, 20), total_amount=1000)
        OrderItem.objects.create(order=big, product=sample_data["lamp"], quantity=100, unit_price=Decimal("30.00"))
        report = anon.post("/api/automation/daily-report/", {"date": "2026-06-03"}, format="json", **self.HDR).data
        assert report["anomaly"] is True and report["pct_drop_vs_7day_avg"] > 30

    def test_emails_recipients_and_logs_the_run(self, anon, sample_data, settings):
        settings.REPORT_RECIPIENTS = ["boss@example.com"]
        report = anon.post("/api/automation/daily-report/", {}, format="json", **self.HDR).data
        assert report["emailed_to"] == ["boss@example.com"]
        assert len(mail.outbox) == 1 and "Revenue" in mail.outbox[0].body
        assert AutomationLog.objects.get().status == "SUCCESS"

    def test_no_email_without_recipients(self, anon, sample_data, settings):
        settings.REPORT_RECIPIENTS = []
        anon.post("/api/automation/daily-report/", {}, format="json", **self.HDR)
        assert mail.outbox == [] and AutomationLog.objects.get().status == "SUCCESS"

    def test_invalid_date_is_rejected(self, anon, sample_data):
        assert anon.post("/api/automation/daily-report/", {"date": "tomorrow"}, format="json", **self.HDR).status_code == 400

    def test_email_failure_is_logged_and_raised(self, sample_data, settings):
        from analytics.reports import send_daily_report
        settings.REPORT_RECIPIENTS = ["boss@example.com"]
        with mock.patch("analytics.reports.send_mail", side_effect=OSError("smtp down")):
            with pytest.raises(OSError):
                send_daily_report()
        assert AutomationLog.objects.get().status == "FAILED"

    def test_management_command_prints_the_report(self, sample_data, capsys):
        from django.core.management import call_command
        call_command("send_daily_report", "--date", "2026-06-03")
        assert "Revenue" in capsys.readouterr().out
