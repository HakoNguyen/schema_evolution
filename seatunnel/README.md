# Apache SeaTunnel Cluster & REST API Guide

This folder contains the Docker Compose infrastructure setup for **Apache SeaTunnel 2.3.13** cluster (Master & Worker).

## 🚀 Services Overview

| Service | Host Port | Role / Description |
| :--- | :--- | :--- |
| **seatunnel-master** | `5801` | **Apache SeaTunnel Cluster Master Node & REST API** |
| **seatunnel-worker-1** | internal | Apache SeaTunnel Execution Worker Node |

---

## 🛠️ How to Start the Cluster

```bash
cd seatunnel
docker compose up -d
```

---

## 📡 Useful SeaTunnel REST API Commands

### 1. Check Node Health State
```powershell
Invoke-RestMethod -Uri "http://localhost:5801/hazelcast/health/node-state"
# Returns: ACTIVE
```

### 2. View Cluster Members & Worker Nodes
```powershell
Invoke-RestMethod -Uri "http://localhost:5801/hazelcast/rest/cluster"
```

### 3. Submit a SeaTunnel Job
```bash
curl -X POST "http://localhost:5801/hazelcast/rest/maps/submit-job" -H "Content-Type: application/json" -d @your_job_config.json
```

---

## 🔗 Integration with Schema Evolution Core

- **Schema Evolution Engine**: Monitors source changes and executes DDL operations (`ALTER TABLE ... ADD COLUMN ...`) on Data Warehouse Target.
- **Apache SeaTunnel Engine**: Distributed data ingestion engine sinking Kafka messages into Target Warehouse.
