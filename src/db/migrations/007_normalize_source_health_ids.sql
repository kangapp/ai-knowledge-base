-- src/db/migrations/007_normalize_source_health_ids.sql

CREATE TEMP TABLE source_health_legacy_normalized AS
SELECT
    CASE
        WHEN source_id = '36氪' THEN 'rss_36kr'
        WHEN source_id IN ('cs.AI', 'cs.CL', 'cs.LG') THEN 'rss_arxiv'
        ELSE source_id
    END AS source_id,
    date,
    0 AS total_collected,
    SUM(approved) AS approved,
    SUM(rejected) AS rejected,
    SUM(failed) AS failed,
    CASE
        WHEN SUM(CASE WHEN avg_score IS NOT NULL THEN approved ELSE 0 END) > 0 THEN
            ROUND(
                SUM(CASE WHEN avg_score IS NOT NULL THEN avg_score * approved ELSE 0 END)
                / SUM(CASE WHEN avg_score IS NOT NULL THEN approved ELSE 0 END),
                1
            )
        ELSE NULL
    END AS avg_score,
    MAX(recorded_at) AS recorded_at
FROM source_health
WHERE source_id IN ('36氪', 'cs.AI', 'cs.CL', 'cs.LG')
GROUP BY
    CASE
        WHEN source_id = '36氪' THEN 'rss_36kr'
        WHEN source_id IN ('cs.AI', 'cs.CL', 'cs.LG') THEN 'rss_arxiv'
        ELSE source_id
    END,
    date;

INSERT INTO source_health
    (source_id, date, total_collected, approved, rejected, failed, avg_score, recorded_at)
SELECT source_id, date, total_collected, approved, rejected, failed, avg_score, recorded_at
FROM source_health_legacy_normalized
WHERE 1=1
ON CONFLICT(source_id, date) DO UPDATE SET
    approved=source_health.approved + excluded.approved,
    rejected=source_health.rejected + excluded.rejected,
    failed=source_health.failed + excluded.failed,
    avg_score=CASE
        WHEN excluded.avg_score IS NULL OR excluded.approved = 0 THEN source_health.avg_score
        WHEN source_health.avg_score IS NULL OR source_health.approved = 0 THEN excluded.avg_score
        ELSE ROUND(
            (source_health.avg_score * source_health.approved + excluded.avg_score * excluded.approved)
            / (source_health.approved + excluded.approved),
            1
        )
    END,
    recorded_at=excluded.recorded_at;

DELETE FROM source_health
WHERE source_id IN ('36氪', 'cs.AI', 'cs.CL', 'cs.LG');

DROP TABLE source_health_legacy_normalized;

INSERT OR REPLACE INTO schema_version (version) VALUES (7);
