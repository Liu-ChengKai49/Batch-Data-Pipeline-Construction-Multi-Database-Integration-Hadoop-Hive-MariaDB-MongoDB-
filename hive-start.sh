#!/bin/bash
set -e

echo "Waiting for /user/hive to be available in HDFS..."

# Wait until path exists using correct user
until HADOOP_USER_NAME=hdfs /opt/hadoop-2.7.4/bin/hdfs dfs -test -e /user/hive; do
  echo "/user/hive not found yet. Retrying in 1 second..."
  sleep 1
done

echo "/user/hive is available. Proceeding..."

# Optional: initialize schema only once
if ! /opt/hive/bin/schematool -dbType postgres -info | grep -q "version:"; then
  echo "Initializing Hive metastore schema..."
  /opt/hive/bin/schematool -dbType postgres -initSchema
else
  echo "Hive schema already initialized."
fi

# Start HiveServer2
exec /opt/hive/bin/hiveserver2 --hiveconf hive.root.logger=INFO,console
