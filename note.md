# Stop and restart Docker containers (ensures a clean environment)
docker compose down
docker compose up -d

# View Hive server logs to confirm it started correctly
docker logs -f hive-server


# --------------------------------------------------------------------
# Download NYC Taxi 2019 parquet files from the public TLC dataset
# Save into ./data/nyc-taxi/raw/2019 (relative to project root)
# --------------------------------------------------------------------
mkdir -p ./data/nyc-taxi/raw/2019

for m in $(seq -w 01 12); do
  URL="https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2019-${m}.parquet"
  OUT="./data/nyc-taxi/raw/2019/yellow_tripdata_2019-${m}.parquet"
  echo "Downloading $URL -> $OUT"
  # -fL: fail on HTTP error, follow redirects
  # --retry 3: retry up to 3 times on network errors
  # --retry-delay 2: wait 2 seconds between retries
  # -C -: resume downloads if partial file exists
  curl -fL --retry 3 --retry-delay 2 -C - -o "$OUT" "$URL"
done


# --------------------------------------------------------------------
# Partition the dataset into Hive-friendly directories
# Format: year=YYYY/month=MM
# --------------------------------------------------------------------
for m in $(seq -w 01 12); do
  DST="./data/nyc-taxi/partitioned/year=2019/month=${m}"
  mkdir -p "$DST"
  mv "./data/nyc-taxi/raw/2019/yellow_tripdata_2019-${m}.parquet" "$DST/"
done


# --------------------------------------------------------------------
# Create a working copy of the repo to clean large dataset files
# --------------------------------------------------------------------
cd /mnt/c/Users/harry/Desktop/工作/DE
cp -r Batch-Data-Pipeline-Construction-Multi-Database-Integration-Hadoop-Hive-MariaDB-MongoDB- local-clean-repo
cd local-clean-repo

# Point this copy to the correct remote repository (GitHub)
git remote set-url origin https://github.com/Liu-ChengKai49/Batch-Data-Pipeline-Construction-Multi-Database-Integration-Hadoop-Hive-MariaDB-MongoDB-.git
git remote -v


# --------------------------------------------------------------------
# Remove large data files from the ENTIRE Git history
# (.parquet, .csv) to avoid GitHub's 100MB limit
# --------------------------------------------------------------------
pip install git-filter-repo  # if not installed

git filter-repo --force \
  --path-glob '*.parquet' \
  --path-glob '*.csv' \
  --invert-paths


# --------------------------------------------------------------------
# Clean up leftover original refs and unreachable objects
# --------------------------------------------------------------------
git for-each-ref --format='%(refname)' refs/original | xargs -r -n 1 git update-ref -d
git reflog expire --expire=now --all
git gc --prune=now --aggressive


# --------------------------------------------------------------------
# Force-push cleaned branch to remote to replace old history
# (required after removing large files from history)
# --------------------------------------------------------------------
git push --force-with-lease origin feature/step2b-nyc-taxi-data
