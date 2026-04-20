```sql
SHOW TABLES FROM online
```


Query id: 29156b2f-498c-41b5-9428-7f7a7bc395a6
```
   ┌─name──────────────┐
1. │ anomaly_blocks    │
2. │ block_event_stats │
3. │ hdfs_logs         │
4. │ kafka_hdfs_logs   │
5. │ mv_block_stats    │
6. │ mv_hdfs_logs      │
   └───────────────────┘
```
  



```sql
SELECT
    block_id,
    sumIf(cnt, event_id = 'E1') AS E1,
    sumIf(cnt, event_id = 'E2') AS E2,
    sumIf(cnt, event_id = 'E3') AS E3,
    sumIf(cnt, event_id = 'E4') AS E4,
    sumIf(cnt, event_id = 'E5') AS E5,
    sumIf(cnt, event_id = 'E6') AS E6,
    sumIf(cnt, event_id = 'E7') AS E7,
    sumIf(cnt, event_id = 'E8') AS E8,
    sumIf(cnt, event_id = 'E9') AS E9,
    sumIf(cnt, event_id = 'E10') AS E10,
    sumIf(cnt, event_id = 'E11') AS E11,
    sumIf(cnt, event_id = 'E12') AS E12,
    sumIf(cnt, event_id = 'E13') AS E13,
    sumIf(cnt, event_id = 'E14') AS E14,
    sumIf(cnt, event_id = 'E15') AS E15,
    sumIf(cnt, event_id = 'E16') AS E16,
    sumIf(cnt, event_id = 'E17') AS E17,
    sumIf(cnt, event_id = 'E18') AS E18,
    sumIf(cnt, event_id = 'E19') AS E19,
    sumIf(cnt, event_id = 'E20') AS E20,
    sumIf(cnt, event_id = 'E21') AS E21,
    sumIf(cnt, event_id = 'E22') AS E22,
    sumIf(cnt, event_id = 'E23') AS E23,
    sumIf(cnt, event_id = 'E24') AS E24,
    sumIf(cnt, event_id = 'E25') AS E25,
    sumIf(cnt, event_id = 'E26') AS E26,
    sumIf(cnt, event_id = 'E27') AS E27,
    sumIf(cnt, event_id = 'E28') AS E28,
    sumIf(cnt, event_id = 'E29') AS E29,
    max(last_updated) AS last_updated
FROM online.block_event_stats
GROUP BY block_id
ORDER BY block_id ASC
```


Query id: d8f4fc2b-9c24-40fc-9a09-75241e0ae5f3
```
   ┌─block_id─┬─E1─┬─E2─┬─E3─┬─E4─┬─E5─┬─E6─┬─E7─┬─E8─┬─E9─┬─E10─┬─E11─┬─E12─┬─E13─┬─E14─┬─E15─┬─E16─┬─E17─┬─E18─┬─E19─┬─E20─┬─E21─┬─E22─┬─E23─┬─E24─┬─E25─┬─E26─┬─E27─┬─E28─┬─E29─┬────────last_updated─┐
1. │ blk_456  │  0 │  1 │  0 │  0 │  0 │  0 │  0 │  0 │  0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │ 2026-04-20 11:18:22 │
   └──────────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────────────────────┘

```

1 row in set. Elapsed: 0.018 sec. 