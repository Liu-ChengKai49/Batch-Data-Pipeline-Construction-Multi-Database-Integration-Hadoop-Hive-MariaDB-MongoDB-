#!/usr/bin/env bash
set -euo pipefail
set -x

# Confirm driver jar exists
ls -l /opt/hive/lib/mysql-connector-j-8.4.0.jar

NN=hdfs://namenode:9000
HDFS="/opt/hadoop/bin/hdfs"
DFS="$HDFS dfs -fs $NN"
DFSADMIN="$HDFS dfsadmin -fs $NN"

echo "Waiting for HDFS..."
until $DFS -ls / >/dev/null 2>&1; do
  echo "HDFS not ready; retrying..."
  sleep 2
done

# Ensure NN out of safemode
$DFSADMIN -safemode wait

# --- Bootstrap HDFS as superuser (root) ---
export HADOOP_USER_NAME=root

# /tmp for Hive/MapReduce
$DFS -mkdir -p /tmp || true
$DFS -chmod 1777 /tmp || true

# **Warehouse path must match hive-site.xml**
WAREHOUSE=/user/hive/warehouse
$DFS -mkdir -p "$WAREHOUSE" || true
$DFS -chmod -R 777 /user/hive || true
$DFS -chown -R hive:supergroup /user/hive || true

# (Optional scratch/external dirs)
$DFS -mkdir -p /tmp/hive || true
$DFS -chmod -R 1777 /tmp/hive || true
$DFS -mkdir -p /user/hive/external || true
$DFS -chmod -R 777 /user/hive/external || true

unset HADOOP_USER_NAME
# --- end bootstrap ---

echo "Checking metastore schema..."
if /opt/hive/bin/schematool -dbType mysql -info >/dev/null 2>&1; then
  SCHEMA_INFO=$(/opt/hive/bin/schematool -dbType mysql -info 2>/dev/null)
  echo "$SCHEMA_INFO"
  if echo "$SCHEMA_INFO" | grep -qi 'version.*3\.1\.0'; then
    echo "Metastore schema is already at 3.1.0. Skipping init."
  else
    echo "Metastore schema exists but is not 3.1.0. Upgrading..."
    /opt/hive/bin/schematool -dbType mysql -upgradeSchema -verbose
  fi
else
  echo "No metastore schema detected. Initializing..."
  /opt/hive/bin/schematool -dbType mysql -initSchema -verbose
fi

echo "Starting HiveServer2..."
exec /opt/hive/bin/hiveserver2 --hiveconf hive.root.logger=INFO,console
