-- ============================================
-- SMARTSALES: BUSINESS KPI QUERIES
-- Day 11
-- ============================================


-- ============================================
-- KPI 1: Total Revenue & Total Orders (all-time)
-- ============================================
SELECT 
    SUM(total_revenue) AS total_revenue,
    SUM(total_orders) AS total_orders
FROM vw_daily_sales;


-- ============================================
-- KPI 2: Average Order Value (AOV)
-- Formula: Revenue / Number of Orders
-- ============================================
SELECT 
    SUM(total_revenue) / SUM(total_orders) AS aov
FROM vw_daily_sales;


-- ============================================
-- KPI 3: Return Rate (store-wide)
-- Formula: Returned Orders / Total Orders
-- ============================================
WITH returned_orders AS (
    SELECT COUNT(DISTINCT order_id) AS returned_order_count
    FROM orders_return
),
total_orders AS (
    SELECT COUNT(*) AS total_order_count
    FROM orders_order
)
SELECT 
    returned_orders.returned_order_count,
    total_orders.total_order_count,
    ROUND(
        (returned_orders.returned_order_count::NUMERIC / total_orders.total_order_count) * 100, 
        2
    ) AS return_rate_pct
FROM returned_orders, total_orders;


-- ============================================
-- KPI 4: Repeat Customer Rate
-- Formula: Customers with 2+ orders / Total Customers
-- ============================================
WITH repeat_customers AS (
    SELECT COUNT(*) AS repeat_customer_count
    FROM vw_customer_metrics
    WHERE total_orders >= 2
),
all_customers AS (
    SELECT COUNT(*) AS total_customer_count
    FROM vw_customer_metrics
)
SELECT 
    repeat_customers.repeat_customer_count,
    all_customers.total_customer_count,
    ROUND(
        (repeat_customers.repeat_customer_count::NUMERIC / all_customers.total_customer_count) * 100, 
        2
    ) AS repeat_customer_rate_pct
FROM repeat_customers, all_customers;


-- ============================================
-- KPI 5: Total Profit & Profit Margin
-- Formula: Profit = Revenue - Cost | Margin = Profit / Revenue
-- ============================================
SELECT 
    SUM(i.quantity * i.unit_price) - SUM(i.quantity * p.cost) AS total_profit,
    ROUND(
        (SUM(i.quantity * i.unit_price) - SUM(i.quantity * p.cost)) 
        / SUM(i.quantity * i.unit_price) * 100, 
        2
    ) AS profit_margin_pct
FROM orders_orderitem i
JOIN products_product p ON i.product_id = p.id;


-- ============================================
-- KPI 6: Customer Lifetime Value (CLV)
-- Formula: Average revenue generated per customer
-- ============================================
SELECT 
    AVG(total_revenue) AS average_revenue
FROM vw_customer_metrics;