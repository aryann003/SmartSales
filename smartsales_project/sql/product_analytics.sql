-- ============================================
-- SMARTSALES: PRODUCT ANALYTICS
-- ============================================


-- ============================================
-- CHALLENGE 1: Product-Level Revenue, Cost & Profit
-- ============================================
CREATE VIEW vw_product_profit AS
SELECT
    p.id AS product_id,
    p.name AS product_name,
    SUM(i.quantity * i.unit_price) AS total_revenue,
    SUM(i.quantity * p.cost) AS total_cost,
    SUM(i.quantity * i.unit_price) - SUM(i.quantity * p.cost) AS total_profit
FROM orders_orderitem i
JOIN products_product p ON p.id = i.product_id
GROUP BY p.id, p.name;


-- ============================================
-- CHALLENGE 2: Category-Level Rollup
-- ============================================
CREATE VIEW vw_category_performance AS
SELECT
    c.id AS category_id,
    c.name AS category_name,
    SUM(i.quantity * i.unit_price) AS total_revenue,
    SUM(i.quantity * p.cost) AS total_cost,
    SUM(i.quantity * i.unit_price) - SUM(i.quantity * p.cost) AS total_profit
FROM orders_orderitem i
JOIN products_product p ON p.id = i.product_id
JOIN products_category c ON p.category_id = c.id
GROUP BY c.id, c.name
ORDER BY total_revenue DESC;


-- ============================================
-- CHALLENGE 3: Bottom 10 Products (lowest revenue)
-- Reuses vw_product_performance from Day 10
-- ============================================
CREATE VIEW vw_bottom_products AS
SELECT 
    product_id,
    product_name,
    total_revenue,
    total_quantity_sold,
    RANK() OVER (ORDER BY total_revenue ASC) AS bottom_rank
FROM vw_product_performance;


-- ============================================
-- CHALLENGE 4: Full Combined Product Analytics View
-- Merges vw_product_performance + vw_product_profit + vw_returns (Day 10)
-- ============================================
CREATE VIEW vw_product_analytics AS
SELECT 
    pp.product_id,
    pp.product_name,
    pp.total_revenue,
    pp.total_quantity_sold,
    pp.revenue_rank,
    pf.total_cost,
    pf.total_profit,
    r.total_sold,
    r.total_returned,
    r.return_rate_pct
FROM vw_product_performance pp
JOIN vw_product_profit pf ON pp.product_id = pf.product_id
JOIN vw_returns r ON pp.product_id = r.product_id;


-- SELECT AVG(return_rate_pct) FROM vw_product_analytics;

SELECT *
FROM vw_product_analytics
WHERE return_rate_pct > 10
ORDER BY return_rate_pct DESC;


-- ============================================
