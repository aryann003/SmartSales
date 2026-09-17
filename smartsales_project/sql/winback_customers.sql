DROP VIEW IF EXISTS vw_winback_candidates;

CREATE VIEW vw_winback_candidates AS
SELECT customer_id, customer_name, recency, frequency, monetary, customer_segment
FROM vw_rfm_segments
WHERE customer_segment = 'At Risk'
  AND monetary_score >= 4
ORDER BY monetary DESC
LIMIT 20;