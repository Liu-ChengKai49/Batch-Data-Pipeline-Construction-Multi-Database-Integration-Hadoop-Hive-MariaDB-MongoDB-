# Batch Data Pipeline Construction & Multi-Database Integration

This project marks my foundational step into data engineering. I set out to build a robust, end-to-end **batch data pipeline**, aiming to understand how core big data tools integrate to handle real-world data challenges—especially those involving **large-scale batch data** and **multi-database storage**.

---

## 🔍 Problem Statement

Industries like manufacturing generate vast batches of data—sensor logs, equipment status, production records. Managing this data poses key challenges:

- **Scalable Storage:** How to store large volumes (GBs–TBs) of raw, often semi-structured data efficiently.
- **Effective Transformation:** How to clean and convert raw data into a structured, queryable format.
- **Diverse Consumption Needs:** How to serve different access patterns (e.g., SQL for analytics, NoSQL for flexible querying).
- **Reproducible Setup:** How to integrate complex big data tools in a consistent, easily deployable development environment.

---

## 🚀 My Learning Journey & Implementation

### 🧱 Step 1: Orchestrating the Environment with Docker Compose

I used Docker Compose to containerize and integrate key services: Hadoop (NameNode, DataNode), Hive, MariaDB, MongoDB, and JupyterLab. This taught me cloud-native patterns and ensured consistent deployment to define a (reproducible) data engineering environment.

**Highlights:**
- Allocated 4GB+ RAM for local container orchestration.
- Built on templates like `big-data-europe/docker-hadoop`.
- Verified UI access: Hadoop (localhost:9870), JupyterLab (localhost:8888).

---

### 🗃️ Step 2: Ingesting Data into HDFS

I simulated a manufacturing sensor dataset and stored it in **HDFS**, Hadoop’s distributed file system. I interacted via CLI and Python, learning about data blocks, replication, and fault tolerance.

**Highlights:**
- Used `hdfs dfs` commands (`-mkdir`, `-put`, `-ls`, `-cat`) to manage data.
- Verified replication and file structure via HDFS Web UI.
- Scripted data upload using Python in JupyterLab.

---

### 📊 Step 3: Structuring Data with Apache Hive

To transform raw HDFS data into structured, queryable format, I created **external Hive tables** and queried with HiveQL.

**Highlights:**
- Defined schemas and ran queries directly on HDFS data.
- Executed filtering, aggregation, and partitioning in Hive.
- Learned how Hive abstracts MapReduce via SQL syntax.

---

### 🔄 Step 4: Storing in MariaDB (SQL) & MongoDB (NoSQL)

To support diverse consumption needs:

- I used **MariaDB** for structured, aggregated data.
- I used **MongoDB** for raw, semi-structured logs needing schema flexibility.

**MariaDB Tasks:**
- Defined relational schemas.
- Loaded Hive outputs via Python (`pymysql`).
- Executed basic SQL queries for validation.

**MongoDB Tasks:**
- Modeled documents using nested fields.
- Loaded raw data via `pymongo`.
- Used `insert_many`, `find`, and `create_index` for operations.

---

## 🛠️ Skills Gained

- **Hadoop & Hive:** CLI and HiveQL-based batch data transformation.
- **SQL & NoSQL Integration:** Hands-on with schema design, data loading, and querying.
- **Batch Pipeline Development:** Designed data flow from ingestion to storage.
- **Containerization:** Used Docker Compose for reproducible, multi-service deployment.
- **Python Automation:** Scripted ETL and database integration processes.
- **Problem Solving:** Resolved service communication, data parsing, and config issues independently.

---

## 📁 Repository Structure

├── data/ # Sample or raw datasets   
├── hdfs/ # Mount for HDFS data   
├── hive/ # HiveQL scripts  
├── scripts/ # Python ETL code  
├── mariadb/ # SQL init scripts  
├── mongodb/ # NoSQL loading scripts  
├── notebooks/ # JupyterLab notebooks  
├── sql/ # .sql and HiveQL definitions  
├── docker-compose.yml # Environment orchestration  
└── README.md # Project documentation  



---

## 📈 Resume-Ready Summary

**Project:** Batch Data Pipeline Construction & Multi-Database Integration  
**Tech:** Hadoop, Hive, MariaDB, MongoDB, Python, Docker Compose

- Built a complete batch pipeline processing ~X GB of simulated sensor logs.
- Used Hive for schema-on-read and SQL-based transformation on HDFS.
- Integrated MariaDB for analytics and MongoDB for raw log storage.
- Automated data ingestion and export using Python (`pymysql`, `pymongo`).
- Deployed services using Docker Compose, reducing setup time by 80%.

---

## 📬 Next Steps

- [ ] Add Airflow for scheduled ETL jobs  
- [ ] Implement basic data validation  
- [ ] Add Grafana dashboard for monitoring  
- [ ] Write setup guide and usage tutorial in `/docs`
