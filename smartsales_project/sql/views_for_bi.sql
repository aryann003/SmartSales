DROP VIEW IF EXISTS vw_daily_sales;
DROP VIEW IF EXISTS vw_monthly_sales;
DROP VIEW IF EXISTS vw_product_performance;
DROP VIEW IF EXISTS vw_customer_metrics;
DROP VIEW IF EXISTS vw_returns;

-- (then all 5 CREATE VIEW statements below)


-- ============================================
-- VIEW 1: Daily Sales
-- ============================================
CREATE VIEW vw_daily_sales AS
SELECT 
    o.order_date AS sale_date,
    SUM(i.quantity * i.unit_price) AS total_revenue,
    COUNT(DISTINCT i.order_id) AS total_orders
FROM orders_order o
JOIN orders_orderitem i ON o.id = i.order_id
GROUP BY o.order_date
ORDER BY o.order_date DESC;


-- ============================================
-- VIEW 2: Monthly Sales + MoM Growth
-- ============================================
CREATE VIEW vw_monthly_sales AS
WITH monthly AS (
    SELECT 
        DATE_TRUNC('month', o.order_date) AS sale_month,
        SUM(i.quantity * i.unit_price) AS total_revenue
    FROM orders_order o
    JOIN orders_orderitem i ON o.id = i.order_id
    GROUP BY DATE_TRUNC('month', o.order_date)
)
SELECT 
    sale_month,
    total_revenue,
    LAG(total_revenue) OVER (ORDER BY sale_month) AS previous_month_revenue,
    CASE 
        WHEN LAG(total_revenue) OVER (ORDER BY sale_month) IS NULL THEN NULL
        WHEN LAG(total_revenue) OVER (ORDER BY sale_month) = 0 THEN NULL
        ELSE ROUND(
            ((total_revenue - LAG(total_revenue) OVER (ORDER BY sale_month)) 
            / LAG(total_revenue) OVER (ORDER BY sale_month)) * 100, 2
        )
    END AS mom_growth_pct
FROM monthly
ORDER BY sale_month DESC;


-- ============================================
-- VIEW 3: Product Performance
-- ============================================
CREATE VIEW vw_product_performance AS
WITH revenue AS (
    SELECT 
        p.id AS product_id,
        p.name AS product_name,
        SUM(o.quantity * o.unit_price) AS total_revenue,
        SUM(o.quantity) AS total_quantity_sold
    FROM orders_orderitem o
    LEFT JOIN products_product p ON o.product_id = p.id
    GROUP BY p.id, p.name
)
SELECT 
    *,
    RANK() OVER (ORDER BY total_revenue DESC) AS revenue_rank
FROM revenue;


-- ============================================
-- VIEW 4: Customer Metrics
-- ============================================
CREATE VIEW vw_customer_metrics AS
SELECT 
    c.id AS customer_id,
    c.name AS customer_name,
    COUNT(DISTINCT o.id) AS total_orders,
    SUM(i.quantity * i.unit_price) AS total_revenue,
    MAX(o.order_date) AS last_order_date,
    CASE 
        WHEN SUM(i.quantity * i.unit_price) >= 50000 THEN 'High Value'
        ELSE 'Standard'
    END AS customer_tier
FROM customers_customer c
JOIN orders_order o ON c.id = o.customer_id
JOIN orders_orderitem i ON o.id = i.order_id
GROUP BY c.id, c.name
ORDER BY total_revenue DESC;


-- ============================================
-- VIEW 5: Returns
-- ============================================
CREATE VIEW vw_returns AS
WITH sold AS (
    SELECT 
        product_id,
        SUM(quantity) AS total_sold
    FROM orders_orderitem
    GROUP BY product_id
),
returned AS (
    SELECT 
        product_id,
        SUM(quantity) AS total_returned
    FROM orders_return
    GROUP BY product_id
)
SELECT 
    p.id AS product_id,
    p.name AS product_name,
    COALESCE(sold.total_sold, 0) AS total_sold,
    COALESCE(returned.total_returned, 0) AS total_returned,
    CASE 
        WHEN COALESCE(sold.total_sold, 0) = 0 THEN NULL
        ELSE ROUND((COALESCE(returned.total_returned, 0)::NUMERIC / sold.total_sold) * 100, 2)
    END AS return_rate_pct
FROM products_product p
LEFT JOIN sold ON p.id = sold.product_id
LEFT JOIN returned ON p.id = returned.product_id;