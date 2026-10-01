# SmartSales — Sales Intelligence & Business Automation Platform

An end-to-end sales analytics and automation platform. Django + PostgreSQL run the application and REST API, Python/Pandas and SQL power the analytics, Power BI delivers dashboards, and n8n automates alerts and reports.

**Live demo:** https://smartsales-s06t.onrender.com (free tier, first load may take ~50s to wake)
**n8n instance:** https://smartsales-n8n.onrender.com (free tier; may require a retry if both services are cold-starting at once)

## Problem Statement

A small or medium business needs to manage customers, products, orders and returns, and turn raw sales data into decisions: monitor KPIs, spot unusual sales drops, identify high-value customers, and win back customers who stopped buying. SmartSales moves the business from *raw data → manual analysis → manual reporting* to *data → analytics → automated action*.

## Features

- Django web app: login, dashboard, customers, products, orders, returns
- REST API with JWT authentication and role-based permissions (Admin, Manager, Analyst, Salesperson)
- Pandas ETL pipeline: 1,067,371 raw rows cleaned to 797,815 and bulk-loaded into PostgreSQL
- 12 SQL views: daily/monthly sales, product performance, customer metrics, returns, RFM, anomaly detection, win-back candidates
- RFM customer segmentation (Champions, Loyal Customers, Potential Loyalists, New Customers, At Risk, Lost)
- 5 n8n automations plus an automation-log monitoring table
- 4-page Power BI dashboard on a star schema with 12+ DAX measures

## Architecture

```
                    SMARTSALES
                        |
          +-------------+-------------+
          |             |             |
       Django       Analytics        n8n
          |             |             |
      REST API     Python + SQL   Automation
          |             |             |
          +-------- PostgreSQL -------+
                        |
                        v
                    Power BI
                        |
                        v
                Business Insights
```

- **Django** = application + REST API. **PostgreSQL (Neon)** = database. **Python/Pandas** = data processing. **SQL** = analytics. **Power BI + DAX** = BI. **n8n** = workflow automation (not the backend).
- Power BI connects directly to Neon. n8n reaches data only through the JWT-protected Django API.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django, Django REST Framework, SimpleJWT |
| Database | PostgreSQL (Neon) |
| Analytics | Python, Pandas, SQL |
| BI | Power BI, DAX |
| Automation | n8n (self-hosted) |
| Frontend | HTML, CSS, Bootstrap, JavaScript |
| Deployment | Render (Django), Neon (PostgreSQL) |

## Database Schema

```
Customer 1--* Order 1--* OrderItem *--1 Product *--1 Category
                 |                       |
                 +--* Return *-----------+
```

Core tables: Customer, Category, Product, Order, OrderItem, Return, plus Profile (user roles) and AutomationLog (workflow monitoring).

## Data Pipeline

`data_pipeline/` — `ingestion.py` → `cleaning.py` → `validation.py` → `loader.py`

- Drops rows with missing customer ID or description, removes duplicates, converts dates, removes invalid prices
- Splits returns (negative quantity or "C" invoices) from sales; derives `revenue = quantity × unit_price`
- Bulk-loads customers, products, orders, order items and returns via Django's `bulk_create`
- Result: ~5.9K customers, ~4.6K products, ~44.9K orders, ~779K order items, ~18K returns

## Analytics API

Auth: `POST /api/token/` returns access/refresh JWTs. Send `Authorization: Bearer <access>`.

| Endpoint | Purpose |
|---|---|
| `/api/customers/`, `/api/products/`, `/api/orders/`, `/api/returns/` | CRUD (role-restricted) |
| `/api/analytics/revenue/` | Daily revenue and order counts |
| `/api/analytics/orders/` | Daily order counts |
| `/api/analytics/products/` | Product revenue, profit, return rate |
| `/api/analytics/customers/` | Customer metrics and tiers |
| `/api/analytics/rfm/` | RFM segments |
| `/api/analytics/anomalies/` | 7-day rolling-average drop detection |
| `/api/analytics/winback-candidates/` | At-risk, high-value customers |
| `/api/analytics/log/` (POST) | Workflow logging |

Analytics endpoints require Manager or Analyst role.

## n8n Workflows

Exported (credentials redacted) in `n8n_workflows/`.

1. **High-Value Order Alert** — Django signal → webhook → IF amount > ₹10,000 → email
2. **Daily Sales Report** — schedule → fetch token → revenue API → email
3. **Sales Anomaly Detection** — schedule → anomalies API → IF drop > 30% → email
4. **Customer Win-Back** — schedule → win-back API → aggregate → one internal notification email
5. **Automation Monitoring** — each workflow logs SUCCESS/FAILED/RETRY to `AutomationLog`

## Power BI

Star schema: `FactSales`, `FactReturns`, `DimCustomer`, `DimProduct`, `DimCategory`, `DimOrder`, `DimDate`. Pages: Executive, Customer Intelligence, Product & Inventory, Operations.

_Add screenshots here: `docs/powerbi-executive.png`, `docs/powerbi-customers.png`, `docs/powerbi-products.png`, `docs/powerbi-operations.png`_

## Installation

```bash
git clone https://github.com/aryann003/SmartSales.git
cd SmartSales/smartsales_project    # manage.py lives here
python -m venv venv
venv\Scripts\activate               # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Environment Variables

Create a `.env` file (never commit it):

```
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

## Known Limitations

- Source data is the public Kaggle *Online Retail II* dataset; dates were shifted forward so history ends near today
- Customer names are generated placeholders; all imported orders are `completed`; all products share one "Imported" category
- Django (Render) and n8n (Render, with Supabase as its own metadata store) both run on free tiers that spin down after ~15 minutes of inactivity. The first request after idle time can take 30-50 seconds, and if both services happen to be asleep at the same moment, a workflow call between them can time out before either finishes waking up. A production deployment would use always-on instances or an uptime pinger to avoid this
- Power BI uses Import mode with manual refresh (Power BI Service was unavailable on the student licence)
- `/api/analytics/log/` is open so n8n can post logs; production should use a shared-secret header
- n8n fetches a fresh JWT on each run using stored login credentials

## Future Improvements

- Move Django and n8n to always-on instances (or add an uptime pinger) so cold starts don't cause missed webhooks or scheduled runs
- Power BI scheduled refresh or an n8n-triggered refresh via the Power BI REST API
- Real order-status and category data; multi-item order entry form
- Secure the logging endpoint; token refresh via the refresh-token flow
- Machine learning (churn prediction, demand forecasting) as an extension