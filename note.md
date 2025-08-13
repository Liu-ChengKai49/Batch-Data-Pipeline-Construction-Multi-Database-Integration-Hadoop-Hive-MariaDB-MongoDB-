docker compose down
docker compose up -d

# docker logs -f hive-server


# From the project root (same level as docker-compose.yml)
mkdir -p ./data/nyc-taxi/raw/2019

for m in $(seq -w 01 12); do
  URL="https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-${m}.parquet"
  OUT="./data/nyc-taxi/raw/2019/yellow_tripdata_2019-${m}.parquet"
  echo "Downloading $URL -> $OUT"
  curl -fL --retry 3 --retry-delay 2 -C - -o "$OUT" "$URL"
done



for m in $(seq -w 01 12); do
  DST="./data/nyc-taxi/partitioned/year=2019/month=${m}"
  mkdir -p "$DST"
  mv "./data/nyc-taxi/raw/2019/yellow_tripdata_2019-${m}.parquet" "$DST/"
done


cd /mnt/c/Users/harry/Desktop/工作/DE
cp -r Batch-Data-Pipeline-Construction-Multi-Database-Integration-Hadoop-Hive-MariaDB-MongoDB- local-clean-repo
cd local-clean-repo


git remote set-url origin https://github.com/Liu-ChengKai49/Batch-Data-Pipeline-Construction-Multi-Database-Integration-Hadoop-Hive-MariaDB-MongoDB-.git
git remote -v


pip install git-filter-repo  # if not installed

git filter-repo --force \
  --path-glob '*.parquet' \
  --path-glob '*.csv' \
  --invert-paths


git for-each-ref --format='%(refname)' refs/original | xargs -r -n 1 git update-ref -d
git reflog expire --expire=now --all
git gc --prune=now --aggressive


git push --force-with-lease origin feature/step2b-nyc-taxi-data
