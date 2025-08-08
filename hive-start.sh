#!/usr/bin/env bash
set -euo pipefail
set -x

# Confirm driver jar exists
ls -l /opt/hive/lib/mysql-connector-j-8.4.0.jar

echo "Waiting for HDFS..."
until /opt/hadoop/bin/hdfs dfs -ls hdfs://namenode:9000/ >/dev/null 2>&1; do
  echo "HDFS not ready; retrying..."
  sleep 2
done

# If using Hive 3 default:
WAREHOUSE=/warehouse/tablespace/managed/hive
/opt/hadoop/bin/hdfs dfs -mkdir -p "$WAREHOUSE" || true
/opt/hadoop/bin/hdfs dfs -chmod -R 777 /warehouse || true

# # Ensure warehouse dirs
# HADOOP_USER_NAME=hdfs /opt/hadoop/bin/hdfs dfs -mkdir -p /user/hive/warehouse || true
# HADOOP_USER_NAME=hdfs /opt/hadoop/bin/hdfs dfs -chmod -R 777 /user/hive || true

echo "Checking metastore schema..."
if /opt/hive/bin/schematool -dbType mysql -info >/dev/null 2>&1; then
  # schematool -info succeeded: schema exists. Decide whether to upgrade or skip.
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