#!/usr/bin/env bash
set -euo pipefail
set -x

# Try to find a JDBC driver jar (either MySQL or MariaDB)
JAR_PATH=""
if [ -f /opt/hive/lib/mysql-connector-j-8.4.0.jar ]; then
  JAR_PATH=/opt/hive/lib/mysql-connector-j-8.4.0.jar
elif [ -f /opt/hive/lib/mariadb-java-client-3.5.4.jar ]; then
  JAR_PATH=/opt/hive/lib/mariadb-java-client-3.5.4.jar
fi

if [ -n "${JAR_PATH}" ]; then
  ls -l "$JAR_PATH"
  export HIVE_AUX_JARS_PATH="$JAR_PATH"
else
  echo "No JDBC driver jar found in /opt/hive/lib (mysql-connector-j-8.4.0.jar or mariadb-java-client-3.5.4.jar)."
  exit 1
fi

echo "Waiting for HDFS to respond..."
until /opt/hadoop-2.7.4/bin/hdfs dfs -ls / >/dev/null 2>&1; do
  echo "HDFS not ready; retrying..."
  sleep 2
done

# Ensure warehouse dirs (retry until datanode write path is ready)
for i in {1..30}; do
  if HADOOP_USER_NAME=hdfs /opt/hadoop-2.7.4/bin/hdfs dfs -mkdir -p /user/hive/warehouse; then
    HADOOP_USER_NAME=hdfs /opt/hadoop-2.7.4/bin/hdfs dfs -chmod -R 777 /user/hive || true
    break
  fi
  echo "HDFS mkdir failed (attempt $i). Retrying in 2s…"
  sleep 2
done

echo "Initializing metastore (mysql)..."
for i in {1..20}; do
  if /opt/hive/bin/schematool -dbType mysql -initSchema -verbose; then
    echo "Metastore schema initialized."
    break
  fi
  echo "schematool failed (attempt $i). Retrying in 3s..."
  sleep 3
done

echo "Starting HiveServer2..."
exec /opt/hive/bin/hiveserver2 --hiveconf hive.root.logger=INFO,console
