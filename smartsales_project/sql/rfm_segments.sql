-- ============================================
-- SMARTSALES: RFM SEGMENTATION VIEW
-- ============================================


DROP VIEW IF EXISTS vw_rfm_segments;


CREATE VIEW vw_rfm_segments AS
WITH reference_date AS (
    SELECT MAX(order_date) AS max_date
    FROM orders_order
),
rfm_base AS (
    SELECT 
        cm.customer_id,
        cm.customer_name,
        (reference_date.max_date - cm.last_order_date) AS recency,
        cm.total_orders AS frequency,
        cm.total_revenue AS monetary
    FROM vw_customer_metrics cm, reference_date
),
rfm_scored AS (
    SELECT 
        *,
        NTILE(5) OVER (ORDER BY recency DESC) AS recency_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS frequency_score,
        NTILE(5) OVER (ORDER BY monetary ASC) AS monetary_score
    FROM rfm_base
)
SELECT 
    customer_id,
    customer_name,
    recency,
    frequency,
    monetary,
    recency_score,
    frequency_score,
    monetary_score,
    CASE 
        WHEN recency_score >= 4 AND frequency_score >= 4 AND monetary_score >= 4 THEN 'Champions'
        WHEN frequency_score >= 4 AND monetary_score >= 3 THEN 'Loyal Customers'
        WHEN recency_score >= 4 AND frequency_score <= 2 THEN 'New Customers'
        WHEN recency_score >= 3 AND frequency_score >= 3 THEN 'Potential Loyalists'
        WHEN recency_score <= 2 AND (frequency_score >= 3 OR monetary_score >= 3) THEN 'At Risk'
        ELSE 'Lost'
    END AS customer_segment
FROM rfm_scored;