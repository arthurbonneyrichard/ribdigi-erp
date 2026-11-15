# Restore drill — 15 November 2026

**Verdict: pass.**
- A full database backup restored onto a separate server with every table identical and the books balanced.
- It took this release's migrations forwards and backwards.
- The app started on it and served requests.
- The per-company backup and restore passed on real Postgres (54 of 54).

**Not yet done: the same drill on production.** That needs the owner to run `ops/dr/production_restore_drill.sh` on the production host. It is read-only on production: it restores into a throwaway container and removes it afterwards.

## 1. Whole-database drill (local stack, real data)

Source: the local `ribdigi_erp` database (59 MB, 255 tables, 27,318 rows, 25 companies, 533 journal entries, 61 invoices, 190 till sales).

Target: a throwaway Postgres 16 container on a private Docker network, with no host ports. The earlier drill (5 Oct) stopped because there was no such server. That gap is closed.

| Step | Result | Time |
| --- | --- | ---: |
| Backup (`pg_dump -Fc`) | 3.29 MB file, SHA-256 checked again after copying | 2.7 s |
| Restore (`pg_restore --exit-on-error`) | exit 0 | 44.3 s |
| Row counts, all 255 tables | identical | — |
| Contents, all 255 tables (md5 of every row) | identical | — |
| Books on the copy | 0 unbalanced journal entries; 0 companies out of balance; 0 orphan journal lines | — |
| App's own trial balance, every company | 25 of 25 balance | — |
| Upgrade the copy to this release (0182 → 0186, including the 15 Nov hotel, restaurant, retail and bakery migrations) | clean | 23.5 s |
| Roll back (0186 → 0182) and upgrade again | clean | — |
| Start the API on the restored copy | `/health` 200, `/health/ready` ok | 17 s |

**Measured recovery time (RTO), local size:** about 1.5 minutes from backup file to a serving API (restore 44 s + migrate 24 s + boot 17 s). Production will take longer as the data grows. The production script reports its own times.

**Recovery point (RPO):** daily backups at 02:00 UTC (on by default since 14 Nov) can lose up to a day. For about 15 minutes, turn on WAL archiving as in `docs/DR_WAL_PITR_RUNBOOK.md`. Whether production archives WAL is not checked here.

## 2. Per-company backup drill (`.ribbak`), on real Postgres

The runbook's drill: create a backup, simulate loss, dry-run, restore with `RESTORE`, verify, and check that another company is untouched and that a foreign backup id gives 404.

It ran as the 13 backup and restore test files against a throwaway Postgres database (`TEST_DATABASE_URL`), not SQLite: **54 passed, 0 failed** (712 s).

## 3. The production script, checked before use

`ops/dr/production_restore_drill.sh` was run against the local stack standing in for production.

- **Pass path:** run with an image of this release's code. Result: `backup_seconds=2`, `restore_seconds=28`, 255 tables matching and identical, books at 0, `migrated_to=20261115_0186 (head)` in 8 s, `api_health=OK`, **`RESULT=PASS`**.
- **Fail path:** with an old image that has two migration heads, it reports `migrate=FAILED` and `RESULT=FAIL`. Its first version printed PASS here, and that is fixed.
- Its books checks print `unbalanced_entries|0`, `unbalanced_companies|0` and `orphan_journal_lines|0`, and fail the drill if any is not 0.

### Running it on production (owner)

```sh
# on the production host, from the repo checkout of the release about to deploy
PROD_PG_CONTAINER=<production postgres container> PROD_PG_USER=ribdigi \
API_IMAGE=<backend image of the release> \
sh ops/dr/production_restore_drill.sh ribdigi_erp <each desk database, if separate>
```

Run it at a quiet hour: sales taken during the run can make a busy table's count differ (the report names the table). Keep `report.txt`. A pass is `RESULT=PASS`, all contents identical (or differences only in tables written to during the run), books at 0, migrations clean and the API healthy. Repeat each quarter and before each release that changes migrations.
