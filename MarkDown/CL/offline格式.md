```shell
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
    sumIf(cnt, event_id = 'E29') AS E29
FROM offline.block_event_stats
GROUP BY block_id
```


Query id: 09735a72-38d9-453f-b7df-9512d457d2bc
```
   ┌─block_id─────────────────┬─E1─┬─E2─┬─E3─┬─E4─┬─E5─┬─E6─┬─E7─┬─E8─┬─E9─┬─E10─┬─E11─┬─E12─┬─E13─┬─E14─┬─E15─┬─E16─┬─E17─┬─E18─┬─E19─┬─E20─┬─E21─┬─E22─┬─E23─┬─E24─┬─E25─┬─E26─┬─E27─┬─E28─┬─E29─┐
1. │ blk_-3544583377289625738 │  0 │  0 │  0 │  0 │  2 │  0 │  0 │  0 │  0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │
2. │ blk_-1608999687919862906 │  0 │  0 │  0 │  0 │  8 │  2 │  0 │  0 │  6 │   0 │   6 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   2 │   0 │   0 │   0 │   6 │   0 │   0 │   0 │
3. │ blk_7503483334202473044  │  0 │  0 │  0 │  0 │  6 │  0 │  0 │  0 │  0 │   0 │   2 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   2 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │
   └──────────────────────────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘

```

3 rows in set. Elapsed: 0.013 sec. 






```shell
SELECT
    batch_id,
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
FROM offline.block_event_stats
GROUP BY
    batch_id,
    block_id
ORDER BY
    batch_id ASC,
    block_id ASC
```


Query id: df687430-a16d-44f6-90e8-40c08ce122b0
```
   ┌───batch_id─┬─block_id─────────────────┬─E1─┬─E2─┬─E3─┬─E4─┬─E5─┬─E6─┬─E7─┬─E8─┬─E9─┬─E10─┬─E11─┬─E12─┬─E13─┬─E14─┬─E15─┬─E16─┬─E17─┬─E18─┬─E19─┬─E20─┬─E21─┬─E22─┬─E23─┬─E24─┬─E25─┬─E26─┬─E27─┬─E28─┬─E29─┬────────last_updated─┐
1. │ 1776612024 │ blk_-1608999687919862906 │  0 │  0 │  0 │  0 │  4 │  1 │  0 │  0 │  3 │   0 │   3 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   1 │   0 │   0 │   0 │   3 │   0 │   0 │   0 │ 2026-04-19 15:20:34 │
2. │ 1776612024 │ blk_-3544583377289625738 │  0 │  0 │  0 │  0 │  1 │  0 │  0 │  0 │  0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │ 2026-04-19 15:20:34 │
3. │ 1776612024 │ blk_7503483334202473044  │  0 │  0 │  0 │  0 │  3 │  0 │  0 │  0 │  0 │   0 │   1 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   1 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │ 2026-04-19 15:20:34 │
4. │ 1776646241 │ blk_-1608999687919862906 │  0 │  0 │  0 │  0 │  4 │  1 │  0 │  0 │  3 │   0 │   3 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   1 │   0 │   0 │   0 │   3 │   0 │   0 │   0 │ 2026-04-20 00:50:46 │
5. │ 1776646241 │ blk_-3544583377289625738 │  0 │  0 │  0 │  0 │  1 │  0 │  0 │  0 │  0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │ 2026-04-20 00:50:46 │
6. │ 1776646241 │ blk_7503483334202473044  │  0 │  0 │  0 │  0 │  3 │  0 │  0 │  0 │  0 │   0 │   1 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │   1 │   0 │   0 │   0 │   0 │   0 │   0 │   0 │ 2026-04-20 00:50:46 │
   └────────────┴──────────────────────────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────────────────────┘

```

6 rows in set. Elapsed: 0.032 sec. 