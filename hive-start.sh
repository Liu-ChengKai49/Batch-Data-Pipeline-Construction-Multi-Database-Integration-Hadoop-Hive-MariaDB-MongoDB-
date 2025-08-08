#!/usr/bin/env bash
set -euo pipefail
set -x

export HIVE_CONF_DIR=/opt/hive/conf

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
$DFS -mkdir -p /tmp || true
$DFS -chmod 1777 /tmp || true
WAREHOUSE=/user/hive/warehouse
$DFS -mkdir -p "$WAREHOUSE" || true
$DFS -chmod -R 777 /user/hive || true
$DFS -chown -R hive:supergroup /user/hive || true
$DFS -mkdir -p /tmp/hive || true
$DFS -chmod -R 1777 /tmp/hive || true
$DFS -mkdir -p /user/hive/external || true
$DFS -chmod -R 777 /user/hive/external || true
unset HADOOP_USER_NAME
# --- end bootstrap ---

# Make the JDBC driver visible to schematool
export HADOOP_CLASSPATH=/opt/hive/lib/mysql-connector-j-8.4.0.jar

echo "Initializing Hive metastore schema..."
if ! /opt/hive/bin/schematool -dbType mysql -info >/dev/null 2>&1; then
  /opt/hive/bin/schematool -dbType mysql -initSchema
else
  echo "Hive schema already initialized."
fi

#Optional: silence beeline home warning
mkdir -p /home/hive/.beeline || true

echo "Starting HiveServer2..."
exec /opt/hive/bin/hiveserver2 \
  --hiveconf hive.root.logger=INFO,console \
  --hiveconf hive.server2.transport.mode=binary \
  --hiveconf hive.server2.thrift.port=10000 \
  --hiveconf hive.server2.thrift.bind.host=0.0.0.0 \
  --hiveconf hive.aux.jars.path=file:///opt/hive/lib/mysql-connector-j-8.4.0.jar
