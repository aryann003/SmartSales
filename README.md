# SmartSales: Sales Intelligence & Business Automation Platform

[![CI](https://github.com/aryann003/SmartSales/actions/workflows/ci.yml/badge.svg)](https://github.com/aryann003/SmartSales/actions/workflows/ci.yml)

A sales operations and analytics platform. **Django + PostgreSQL** run the web app and REST API, **Pandas + SQL** power the analytics, **Power BI** delivers dashboards, and an **automation layer** (signed webhooks, scheduled reports, n8n workflows) turns data into action.

**Live demo:** https://smartsales-s06t.onrender.com (free tier; the first load can take about a minute)
Demo logins (password `DemoPass123!`): `demo_admin`, `demo_manager`, `demo_analyst`, `demo_salesperson`. API docs: `/api/docs/`.

## What makes it more than CRUD

- **Role-based access control** with a documented matrix, enforced on every endpoint and covered by tests.
- **A SQL analytics layer** (12 views with CTEs and window functions) created by a migration, so any fresh database works.
- **A transactional, idempotent ETL pipeline**: 1,067,371 raw rows cleaned to 797,815, loaded all-or-nothing.
- **Reliable automation:** HMAC-signed webhooks, delivered after commit in the background, with retries, exponential backoff and an audit log.
- **A secured scheduled report** that runs from GitHub Actions on a free hosting tier.
- **210 automated tests (97% coverage)** running in CI against PostgreSQL.

## Features

- Django web app: login, dashboard, paginated customer/product/order/return lists, and return recording
- REST API with JWT authentication, throttled login, and OpenAPI docs (Swagger UI at `/api/docs/`)
- RFM customer segmentation (Champions, Loyal Customers, Potential Loyalists, New Customers, At Risk, Lost)
- Sales anomaly detection against a trailing 7-day average, and win-back targeting
- n8n automations plus an automation log for monitoring
- 4-page Power BI dashboard on a star schema with 12+ DAX measures

## Architecture

```
                    SMARTSALES
                        |
          +-------------+-------------+
          |             |             |
       Django       Analytics     Automation
          |             |             |
      REST API     Python + SQL   signed webhooks,
          |             |         daily report, n8n
          +-------- PostgreSQL -------+
                        |
                        v
                    Power BI
```

Django is the application and API, PostgreSQL (Neon) the database, SQL views the analytics, and n8n an optional automation consumer (never the backend). Power BI connects directly to the database.

## Screenshots

| Dashboard | Customers | Products |
| --- | --- | --- |
| ![Dashboard](smartsales_project/docs/dashboard.png) | ![Customers](smartsales_project/docs/customers.png) | ![Products](smartsales_project/docs/products.png) |

| Orders | Returns |
| --- | --- |
| ![Orders](smartsales_project/docs/orders.png) | ![Returns](smartsales_project/docs/returns.png) |

## Access control

Roles live on `Profile.role`. New accounts default to the least privileged business role (`salesperson`); superusers become `admin`.

| Resource | Read | Write |
| --- | --- | --- |
| Customers, orders, order items, returns | any signed-in user | admin, manager, salesperson |
| Products, categories | any signed-in user | admin, manager |
| Analytics endpoints | admin, manager, analyst | read-only |
| Automation endpoints | shared `X-Automation-Token` | shared `X-Automation-Token` |

## Data pipeline

`data_pipeline/`: `ingestion` → `cleaning` → `validation` → `loader`, run with one command:

```bash
python manage.py import_retail_data --file data/online_retail_II.csv [--limit 50000] [--replace]
```

- **Cleaning** drops rows with a missing customer or description, exact duplicates, invalid dates, and non-positive prices; flags returns (negative quantity or an invoice starting with `C`); derives `revenue = quantity x unit_price`.
- **Validation gate** halts the run, and writes nothing, if any check fails, and lists every issue.
- **Loading** uses `bulk_create` in batches inside one transaction, so a failure part-way leaves the database untouched. Re-running is refused unless `--replace` is passed, so data is never silently duplicated.
- On the full dataset (Kaggle *Online Retail II*): 1,067,371 raw rows → 797,815 clean rows → about 5.9K customers, 4.6K products, 44.9K orders, 779K order items, 18K returns.

The CSV is not in the repository. Download it from Kaggle and place it at `smartsales_project/data/online_retail_II.csv`. For a quick demo without it:

```bash
python manage.py seed_demo_data        # ~2,000 realistic orders, one user per role, a deliberate sales dip
```

## SQL analytics layer

The analytics endpoints read from 12 PostgreSQL views (daily and monthly sales with month-over-month growth, product performance and profit, customer metrics and tiers, returns, RFM segments, anomaly detection, win-back candidates). The `.sql` files in `sql/` are the single source of truth. **A migration creates the views**, so a fresh database is fully working after `migrate`. To rebuild them after editing a file:

```bash
python manage.py refresh_sql_views
```

## Analytics API

Authenticate with `POST /api/token/` (returns access and refresh JWTs, rate limited to 10 attempts per minute), then send `Authorization: Bearer <access>`. Interactive docs: `/api/docs/`.

| Endpoint | Purpose |
| --- | --- |
| `/api/customers/`, `/api/products/`, `/api/categories/`, `/api/orders/`, `/api/order-items/`, `/api/returns/` | CRUD (role-restricted, paginated) |
| `/api/analytics/revenue/` | Daily revenue and order counts |
| `/api/analytics/orders/` | Daily order counts |
| `/api/analytics/products/` | Product revenue, profit, return rate |
| `/api/analytics/customers/` | Customer metrics and tiers |
| `/api/analytics/rfm/` | RFM segments |
| `/api/analytics/anomalies/` | Drop versus the trailing 7-day average |
| `/api/analytics/winback-candidates/` | At-risk, high-value customers |
| `/api/analytics/log/` (POST) | Workflows record runs (needs the automation token) |
| `/api/automation/daily-report/` (POST) | Build and email the daily report (needs the automation token) |

If the SQL views are missing (for example on SQLite), analytics endpoints return `503` with an explanatory message instead of crashing.

## Automation

### Signed, reliable order webhooks

When an order is created, Django notifies the configured receiver (for example n8n):

- **Authentic:** every request carries `X-SmartSales-Signature` (`sha256=` HMAC of `timestamp.body`, keyed by `WEBHOOK_SECRET`) and `X-SmartSales-Timestamp`. Receivers should verify the signature and reject timestamps older than 5 minutes (replay protection). `core.automation.verify_signature` is a reference implementation.
- **Non-blocking and correct:** delivery is scheduled with `transaction.on_commit` and runs in a background thread, so a slow receiver never slows down order creation and rolled-back orders never fire a webhook.
- **Resilient:** network errors, `429` and `5xx` responses are retried with exponential backoff (3 attempts by default); other `4xx` responses are not retried.
- **Observable:** every attempt is stored in `AutomationLog` (`SUCCESS`, `RETRY`, `FAILED`).
- Disabled automatically when `N8N_WEBHOOK_URL` is empty.

### Scheduled daily report

`POST /api/automation/daily-report/` builds the report (revenue, orders, average order value, change versus the previous day, returns, top products, and an anomaly alert), emails it to `REPORT_RECIPIENTS`, and logs the run. Render's free tier has no cron jobs, so `.github/workflows/daily-report.yml` calls the endpoint every morning. Set the repository secrets `SMARTSALES_URL` and `AUTOMATION_API_KEY`. Locally: `python manage.py send_daily_report`.

### n8n workflows

Exported (credentials redacted) in `smartsales_project/n8n_workflows/`.

1. **High-Value Order Alert:** Django webhook → IF amount > ₹10,000 → email
   ![High-Value Order Alert](smartsales_project/docs/n8n2.png)
2. **Daily Sales Report:** schedule → fetch token → revenue API → email
   ![Daily Sales Report](smartsales_project/docs/n8n3.png)
3. **Sales Anomaly Detection:** schedule → anomalies API → IF drop > 30% → email
   ![Sales Anomaly Detection](smartsales_project/docs/n8n4.png)
4. **Customer Win-Back:** schedule → win-back API → aggregate → internal notification email
   ![Customer Win-Back](smartsales_project/docs/n8n1.png)
5. **Automation Monitoring:** workflows record SUCCESS / FAILED / RETRY to `AutomationLog` by POSTing to `/api/analytics/log/` with the `X-Automation-Token` header.

> **Upgrading an existing n8n setup:** the log endpoint is now protected. Add the header `X-Automation-Token: <AUTOMATION_API_KEY>` to every n8n HTTP node that calls `/api/analytics/log/`, and set `N8N_WEBHOOK_URL` to your n8n webhook (`.../webhook/new-order`) instead of the old hardcoded localhost address.

## Power BI

Star schema: `FactSales`, `FactReturns`, `DimCustomer`, `DimProduct`, `DimCategory`, `DimOrder`, `DimDate`. Pages: Executive, Customer Intelligence, Product & Inventory, Operations.

![Executive Dashboard](smartsales_project/docs/dashboard1.png)
![Customer Intelligence](smartsales_project/docs/dashboard2.png)
![Product and Inventory](smartsales_project/docs/dashboard3.png)
![Operations](smartsales_project/docs/dashboard4.png)

## Testing

```bash
cd smartsales_project
pip install -r requirements-dev.txt
pytest --cov
```

The suite needs PostgreSQL (the SQL views use Postgres features); `DATABASE_URL` defaults to `postgres://smartsales:smartsales@localhost:5432/smartsales` in `pytest.ini`. It covers the role matrix on every endpoint, API validation, query counts, every SQL view, the ETL pipeline (each cleaning rule, the validation gate, idempotency and transactional rollback), webhook signing, retries and non-blocking delivery, the secured endpoints, and the daily report. CI runs it on every push against a PostgreSQL service container.

## Run locally

**Docker (PostgreSQL included):**

```bash
cd smartsales_project
docker compose up --build
docker compose exec web python manage.py seed_demo_data
```

Open http://localhost:8000 and sign in as `demo_manager` / `DemoPass123!`.

**Without Docker:** create a PostgreSQL database, copy `.env.example` to `.env`, then:

```bash
cd smartsales_project
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

## Deployment (Render + Neon)

`render.yaml` defines the web service. The database is an external PostgreSQL (Neon) so it does not expire like Render's free database.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string (set in the dashboard) |
| `SECRET_KEY`, `AUTOMATION_API_KEY`, `WEBHOOK_SECRET` | Generated by the blueprint |
| `DEBUG` | `False` in production |
| `N8N_WEBHOOK_URL` | Optional: where order webhooks are sent |
| `REPORT_RECIPIENTS` | Optional: daily report email recipients |
| `SEED_DEMO` | `true` seeds demo data on deploy when the database is empty |
| `EMAIL_*` | Optional SMTP settings (the console backend is used otherwise) |

The build runs `bash build.sh` (install, collect static files, migrate, optional seed).

## Known limitations

- The Kaggle dataset has generated customer names, a single "Imported" category, and all orders are `completed`; dates were shifted forward so the history ends near today.
- Free tiers sleep when idle, so the first request can take about a minute. The scheduled report retries to cope with this.
- The anomaly view compares each day to the trailing 7-day average without adjusting for weekends, so quiet weekends can be flagged.
- Order totals are stored on the order and set by the caller or the web form; the API does not recompute them from items.
- Power BI uses Import mode with manual refresh.

## Future improvements

- Recompute order totals from line items; real order statuses and categories
- Always-on hosting for n8n, or move all scheduling into Django
- Weekday-aware anomaly detection
- Machine learning extensions (churn prediction, demand forecasting)
