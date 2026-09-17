-- ============================================
-- SMARTSALES: SALES ANOMALY DETECTION
-- Day 19
-- ============================================

-- Drop any earlier version first, so this is safely re-runnable
DROP VIEW IF EXISTS vw_sales_anomaly;

CREATE VIEW vw_sales_anomaly AS
WITH revenue_with_avg AS (
    SELECT 
        sale_date,
        total_revenue,
        AVG(total_revenue) OVER (
            ORDER BY sale_date 
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS avg_7day_revenue
    FROM vw_daily_sales
)
SELECT 
    sale_date,
    total_revenue,
    ROUND(avg_7day_revenue, 2) AS avg_7day_revenue,
    CASE 
        WHEN avg_7day_revenue IS NULL OR avg_7day_revenue = 0 THEN NULL
        ELSE ROUND(
            ((avg_7day_revenue - total_revenue) / avg_7day_revenue) * 100, 
            2
        )
    END AS pct_drop
FROM revenue_with_avg
ORDER BY sale_date DESC;


-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- See the most recent 10 days with their anomaly calculation
SELECT * FROM vw_sales_anomaly ORDER BY sale_date DESC LIMIT 10;

-- Find any real anomalies (drop greater than 30%)
SELECT * FROM vw_sales_anomaly WHERE pct_drop > 30 ORDER BY sale_date DESC;