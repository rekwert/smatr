UPDATE signals
SET status = 'archived'
WHERE status = 'active'
  AND (
    reason->>'feed' = 'volume_scan'
    OR COALESCE(reason->>'feed', '') = ''
  );

SELECT status, COALESCE(reason->>'feed', '(none)') AS feed, count(*)
FROM signals
GROUP BY 1, 2
ORDER BY 3 DESC;
