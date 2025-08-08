#!/usr/bin/env bash
set -euo pipefail
set -x

# Confirm driver jar exists
ls -l /opt/hive/lib/mariadb-java-client-3.5.4.jar

echo "Waiting for HDFS..."
until /opt/hadoop/bin/hdfs dfs -ls / >/dev/null 2>&1; do
  echo "HDFS not ready; retrying..."
  sleep 2
done

# Ensure warehouse dirs
HADOOP_USER_NAME=hdfs /opt/hadoop/bin/hdfs dfs -mkdir -p /user/hive/warehouse || true
HADOOP_USER_NAME=hdfs /opt/hadoop/bin/hdfs dfs -chmod -R 777 /user/hive || true

echo "Initializing metastore (mysql)..."
for i in {1..20}; do
  if /opt/hive/bin/schematool -dbType mysql -initSchema -verbose; then
    break
  fi
  echo "schematool failed (attempt $i). Retrying in 3s..."
  sleep 3
done

echo "Starting HiveServer2..."
exec /opt/hive/bin/hiveserver2 --hiveconf hive.root.logger=INFO,console
