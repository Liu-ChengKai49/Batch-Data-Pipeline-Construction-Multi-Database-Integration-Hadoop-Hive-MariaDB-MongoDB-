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

I ingested sensor data into HDFS using a staged approach to balance speed and realism.

#### **Phase A — Quick Smoke Test (Simulated CSV)**
I created a small CSV file to validate the pipeline end-to-end with zero external dependencies.

* **Verified HDFS connectivity and permissions:**
    ```bash
    hdfs dfs -mkdir -p /data/sensors
    hdfs dfs -put sensor_data.csv /data/sensors/
    hdfs dfs -ls /data/sensors && hdfs dfs -cat /data/sensors/sensor_data.csv
    ```
* Confirmed replication and block layout in the HDFS Web UI (`localhost:9870`).
* (Optional) Automated this flow via Python `hdfs` client in Jupyter.

This phase was crucial for testing Docker networking, HDFS configs, and authentication before moving on to larger datasets.

#### **Phase B — Real-World Ingestion (Intel Lab Sensor Data)**
I downloaded and organized Intel Lab Sensor Data (wireless sensor network time-series).

* **Standardized Layout:** Structured the data into a partition-friendly layout:
    ```swift
    /data/sensors/dt=YYYY-MM-DD/*.csv
    ```
* **Ingested to HDFS:** Used batch `hdfs dfs -put` commands and verified file counts, sizes, and replication factors with `hdfs dfs -du -h` and `hdfs dfs -stat %r`.
* **Observed Scalability:** Scaled up file sizes to observe HDFS block splitting and confirm stable performance under larger loads.

---

### 📊 Step 3: Structuring Data with Apache Hive

To transform raw HDFS data into a structured, queryable format, I created **external Hive tables** and queried with HiveQL.

* **Highlights:**
    * Defined schemas directly on HDFS data, leveraging Hive’s "schema-on-read" capability.
    * Executed filtering, aggregation, and partitioning in Hive.
    * Learned how Hive abstracts MapReduce with SQL syntax.

---

### 🔄 Step 4: Storing in MariaDB (SQL) & MongoDB (NoSQL)

To support diverse consumption needs, I integrated both MariaDB and MongoDB into the pipeline.

* **MariaDB (Structured Analytics):**
    * Defined relational schemas.
    * Loaded Hive outputs via Python (`pymysql`).
    * Ran basic SQL queries for validation.
* **MongoDB (Flexible Log Storage):**
    * Modeled documents with nested fields.
    * Loaded raw logs via `pymongo`.
    * Used `insert_many`, `find`, and `create_index` for operations.

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
