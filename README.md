# Batch Data Pipeline Construction & Multi-Database Integration

This project marks my foundational step into data engineering. I set out to build a robust, end-to-end **batch data pipeline**, aiming to understand how core big data tools integrate to handle real-world data challenges—especially those involving **large-scale batch data** and **multi-database storage**.

---

## 🔍 Problem Statement

Industries like manufacturing generate vast batches of data—sensor logs, equipment status, production records. Managing this data poses key challenges:

* **Scalable Storage:** How to store large volumes (GBs–TBs) of raw, often semi-structured data efficiently.
* **Effective Transformation:** How to clean and convert raw data into a structured, queryable format.
* **Diverse Consumption Needs:** How to serve different access patterns (e.g., SQL for analytics, NoSQL for flexible querying).
* **Reproducible Setup:** How to integrate complex big data tools in a consistent, easily deployable development environment.

---

## 🚀 My Learning Journey & Implementation

### 🧱 Step 1: Orchestrating the Environment with Docker Compose

I used Docker Compose to containerize and integrate key services: **Hadoop (NameNode, DataNode), Hive, MariaDB, MongoDB, and JupyterLab**. This taught me cloud-native patterns and ensured consistent deployment to define a reproducible data engineering environment.

* **Highlights:**
    * Allocated 4GB+ RAM for local container orchestration.
    * Built on templates like `big-data-europe/docker-hadoop`.
    * Resolved a series of complex configuration issues (timing, networking, and classpaths) to get all services running and communicating correctly.
* **Verified UI access:**
    * Hadoop: `http://localhost:9870`
    * JupyterLab: `http://localhost:8888`

---

### 🗃️ Step 2: Ingesting Data into HDFS

I ingested data into **HDFS** using a staged approach to balance speed and realism.

---

#### **Phase A — Quick Smoke Test (Simulated CSV)**

I created a small CSV file to validate the pipeline end-to-end with zero external dependencies.

* **Verified HDFS connectivity and permissions:**
    ```bash
    hdfs dfs -mkdir -p /data/sensors
    hdfs dfs -put sensor_data.csv /data/sensors/
    hdfs dfs -ls /data/sensors && hdfs dfs -cat /data/sensors/sensor_data.csv
    ```
* Confirmed replication and block layout in the **HDFS Web UI** (`http://localhost:9870`).
* Automated this flow via Python `hdfs` client in **Jupyter**.

This phase was crucial for testing **Docker networking, HDFS configurations, and authentication** before moving on to larger datasets.

---

#### **Phase B — Real-World Ingestion (NYC Taxi Trip Data, 2019)**

I ingested the **NYC Taxi Trip Data** for the year 2019 — a large, publicly available dataset containing hundreds of millions of taxi trip records.

* **Dataset Overview:**
  - **Volume:** ~2.6 GB uncompressed CSV (~130 million rows)
  - **Schema Highlights:** pickup/dropoff timestamps, passenger count, trip distance, fare amount, pickup/dropoff location IDs.

* **Standardized Layout:** Organized the data into a **partition-friendly** directory structure for efficient querying in Hive:
    ```bash
    /data/taxi/year=2019/month=01/*.csv
    /data/taxi/year=2019/month=02/*.csv
    ...
    /data/taxi/year=2019/month=12/*.csv
    ```
* **Ingested to HDFS:** Uploaded monthly CSV files using batch commands and verified ingestion:
    ```bash
    hdfs dfs -put yellow_tripdata_2019-*.csv /data/taxi/year=2019/
    hdfs dfs -du -h /data/taxi/year=2019/
    hdfs dfs -stat %r /data/taxi/year=2019/yellow_tripdata_2019-01.csv
    ```
* **Observed Scalability:** The dataset size allowed me to observe:
  - **HDFS block splitting** across multiple DataNodes.
  - **Replication behavior** in the HDFS Web UI.
  - **Stable performance** under multi-GB ingestion.

---

**Why this dataset:**  
Unlike small datasets, the NYC Taxi Trip Data provides realistic **multi-GB scale**, making it ideal for demonstrating **HDFS’s scalability**, partitioning for Hive, and real-world ETL operations.


---

### 📊 Step 3: Structuring Data with Apache Hive

To transform raw HDFS data into a structured, queryable format, I created **external Hive tables** and queried with HiveQL.

* **Highlights:**
    * Defined schemas directly on HDFS data, leveraging Hive’s "schema-on-read" capability.
    * Executed filtering, aggregation, and partitioning in Hive.
    * Learned how Hive abstracts MapReduce with SQL syntax.





---

### 🔄 Step 4: Storing in MariaDB (SQL) & MongoDB (NoSQL)

To support diverse consumption needs, I built and executed a **complete ETL process** that moves data from Hive/HDFS into relational and document databases for fast, purpose-built querying.

* **MariaDB (Structured Analytics):**

  * Designed a relational schema (`taxi_monthly_summary`) for aggregated analytics.
  * **Extracted** pre-aggregated data from Hive using Python (`pyhive`).
  * **Transformed** data in Hive with SQL (filtering, grouping, NULL handling).
  * **Loaded** results into MariaDB using Python (`pymysql`) with batched, idempotent upserts.
  * Validated loads with basic SQL queries and added indexes for fast retrieval.

* **MongoDB (Flexible Log Storage):**

  * Modeled semi-structured logs as nested JSON documents.
  * **Extracted** raw records from source files.
  * **Transformed** minimal fields for document consistency.
  * **Loaded** documents into MongoDB via Python (`pymongo`) using `insert_many`.
  * Created indexes and ran `find` queries to confirm data integrity and query performance.


---

## 🛠️ Skills Gained

* **Hadoop & Hive:** Command-line and HiveQL-based batch data transformation.
* **SQL & NoSQL Integration:** Hands-on with schema design, data loading, and querying.
* **Batch Pipeline Development:** Designed data flow from ingestion to multi-database storage.
* **Containerization:** Used Docker Compose for reproducible, multi-service deployment.
* **Python Automation:** Scripted ETL and database integration processes.
* **Problem Solving:** Resolved service communication, data parsing, and configuration issues independently.

---

## 📁 Repository Structure

```graphql
├── data/                    # Sample or raw datasets
├── hdfs/                    # HDFS mount
├── hive/                    # HiveQL scripts
├── scripts/                 # Python ETL scripts
├── mariadb/                 # SQL init scripts
├── mongodb/                 # NoSQL loading scripts
├── notebooks/               # Jupyter notebooks
├── sql/                     # SQL and HiveQL definitions
├── docker-compose.yml       # Service orchestration
└── README.md                # Project documentation
```
---

### 📈 Resume-Ready Summary

**Project:** Batch Data Pipeline Construction & Multi-Database Integration  
**Tech Stack:** Hadoop, Hive, MariaDB, MongoDB, Python, Docker Compose

* Built a complete batch pipeline processing a simulated dataset of manufacturing sensor logs.
* Used Hive for schema-on-read SQL transformation directly on HDFS data.
* Integrated MariaDB for structured analytics and MongoDB for raw log storage.
* Automated data ingestion and exports with Python (`pymysql`, `pymongo`).
* Deployed all services via Docker Compose, creating a reproducible environment and demonstrating proficiency in container orchestration.

---

### 📬 Next Steps

* [ ] Add Airflow for scheduled ETL jobs
* [ ] Implement basic data validation
* [ ] Add Grafana dashboard for monitoring
* [ ] Write setup & usage docs in `/docs`




