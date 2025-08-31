from __future__ import annotations
from datetime import datetime
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.bash import BashOperator

DAG_ID = "batch_nyc_taxi_pipeline"
START_DATE = datetime(2025, 1, 1)

with DAG(
    dag_id=DAG_ID,
    start_date=START_DATE,
    schedule_interval=None,  # trigger manually first; add cron later
    catchup=False,
    default_args={"owner": "data-eng"},
    tags=["batch","dq"],
) as dag:

    start = EmptyOperator(task_id="start")

    # ---- Gate 1: Hive DQ (fail if violations_total > 0)


    dq_hive_gate = BashOperator(
        task_id="dq_hive_gate",
        bash_command=r"""
        set -euo pipefail

        # Run everything *inside* the hive-server container so we can see stdout/stderr in Airflow logs
        docker exec -i hive-server bash -lc '
            set -euo pipefail
            export HOME=/tmp

            echo "== Smoke test =="
            /opt/hive/bin/beeline -u "jdbc:hive2://hive-server:10000/" -n hive -p "" \
            --silent=true --showHeader=false --outputformat=tsv2 \
            -e "SELECT 1" 1>/tmp/hive_smoke.tsv 2>/tmp/beeline_smoke.err || true
            echo "stdout:"; cat /tmp/hive_smoke.tsv || true
            echo "stderr:"; cat /tmp/beeline_smoke.err || true
            echo

            echo "== Write DQ SQL =="
            cat >/tmp/hive_checks_labeled.sql <<'"'"'SQL'"'"'
    SET hive.cli.print.header=false;
    USE default;

    WITH
    acc AS (
    SELECT COALESCE(COUNT(*),0) AS bad_time_order
    FROM yellow_taxi
    WHERE year='"'"'2019'"'"' AND tpep_pickup_datetime >= tpep_dropoff_datetime
    ),
    val AS (
    SELECT
        COALESCE(SUM(CASE WHEN trip_distance < 0 OR trip_distance > 300  THEN 1 ELSE 0 END),0) AS bad_trip_distance,
        COALESCE(SUM(CASE WHEN fare_amount   < 0 OR fare_amount   > 1000 THEN 1 ELSE 0 END),0) AS bad_fare_amount
    FROM yellow_taxi
    WHERE year='"'"'2019'"'"'
    ),
    comp AS (
    SELECT
        COALESCE(COUNT(*) - COUNT(tpep_pickup_datetime),0)  AS missing_pickup_ts,
        COALESCE(COUNT(*) - COUNT(tpep_dropoff_datetime),0) AS missing_dropoff_ts,
        COALESCE(COUNT(*) - COUNT(passenger_count),0)       AS missing_pax
    FROM yellow_taxi
    WHERE year='"'"'2019'"'"'
    )
    SELECT 1 AS ord, "accuracy.bad_time_order",               CAST(bad_time_order AS BIGINT)      FROM acc
    UNION ALL SELECT 2, "validity.bad_trip_distance",         CAST(bad_trip_distance AS BIGINT)    FROM val
    UNION ALL SELECT 3, "validity.bad_fare_amount",           CAST(bad_fare_amount AS BIGINT)      FROM val
    UNION ALL SELECT 4, "completeness.missing_pickup_ts",     CAST(missing_pickup_ts AS BIGINT)    FROM comp
    UNION ALL SELECT 5, "completeness.missing_dropoff_ts",    CAST(missing_dropoff_ts AS BIGINT)   FROM comp
    UNION ALL SELECT 6, "completeness.missing_pax",           CAST(missing_pax AS BIGINT)          FROM comp
    UNION ALL SELECT 7, "violations_total",
    CAST(bad_time_order + bad_trip_distance + bad_fare_amount + missing_pickup_ts + missing_dropoff_ts + missing_pax AS BIGINT)
    FROM acc CROSS JOIN val CROSS JOIN comp
    ORDER BY ord;
    SQL

            echo "== Run DQ SQL =="
            /opt/hive/bin/beeline -u "jdbc:hive2://hive-server:10000/" -n hive -p "" \
            --silent=true --showHeader=false --outputformat=tsv2 \
            -f /tmp/hive_checks_labeled.sql \
            1>/tmp/hive_dq.tsv 2>/tmp/beeline.err || true

            echo "=== Metrics (name -> value) ==="
            if [ -s /tmp/hive_dq.tsv ]; then
            awk -F "\t" "{printf \"%-35s %s\n\", \$2, \$3}" /tmp/hive_dq.tsv
            else
            echo "(no rows printed)"
            fi

            echo "=== Raw TSV (metric<TAB>value) ==="
            cat /tmp/hive_dq.tsv || true

            echo "=== Beeline stderr (warnings/errors) ==="
            sed -n "1,200p" /tmp/beeline.err || true
        '

        # Extract violations_total back in the Airflow container and fail fast if > 0
        OUT="$(docker exec -i hive-server bash -lc 'cat /tmp/hive_dq.tsv || true')"
        VIOL="$(printf "%s\n" "$OUT" | awk -F $'\t' '$2=="violations_total"{print $3}')"
        : "${VIOL:=0}"
        echo "violations_total=${VIOL}"
        if [ "${VIOL:-0}" -gt 0 ]; then
            echo "Hive DQ failed (violations_total=${VIOL})"
            exit 1
        fi
        """,
    )

    # ---- Batch load (replace with your spark-submit or load step)
    batch_load = BashOperator(
        task_id="batch_load",
        bash_command=r"""
          set -euo pipefail
          echo ">>> RUN YOUR SPARK JOB HERE (placeholder)"
          # Example:
          # docker compose exec -T spark bash -lc '
          #   /opt/bitnami/spark/bin/spark-submit ... /app/batch/load_nyc_taxi_to_mariadb.py
          # '
        """,
    )

    # ---- Gate 2: MariaDB DQ (fail if violations_total > 0)
# dq_mariadb_gate
    dq_mariadb_gate = BashOperator(
        task_id="dq_mariadb_gate",
        bash_command=r"""
        set -euo pipefail
        OUT="$(docker exec -i mariadb bash -lc '
            mysql -uroot -p"$MARIADB_ROOT_PASSWORD" -D analytics \
            --batch --skip-column-names -e "source /opt/dq/mariadb_checks.sql"
        ')"
        echo "=== MariaDB DQ Raw ==="
        echo "$OUT"
        VIOL="$(printf "%s\n" "$OUT" | awk '{print $NF}' | tail -n1 | tr -dc 0-9)"
        : "${VIOL:=0}"
        echo "violations_total=${VIOL}"
        if [ "$VIOL" -gt 0 ]; then
            echo "MariaDB DQ failed (violations_total=$VIOL)"; exit 1
        fi
        """,
    )



    done = EmptyOperator(task_id="done")
    # start >>  dq_mariadb_gate >> done
    start >> dq_hive_gate >> batch_load >> dq_mariadb_gate >> done
