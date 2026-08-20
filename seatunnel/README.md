# Apache SeaTunnel & StarRocks Stack Integration

This folder contains the Docker Compose infrastructure setup for **Apache SeaTunnel 2.3.13** and **StarRocks 4.0**.

## 🚀 Services Overview

| Service | Host Port | Role / Description |
| :--- | :--- | :--- |
| **starrocks-fe** | `8030`, `9020`, `9030` | StarRocks Frontend Management Node (MySQL Protocol on port 9030) |
| **starrocks-be** | `8040` | StarRocks Backend Storage & Compute Engine |
| **seatunnel-master** | `5801`, `8080` | Apache SeaTunnel Cluster Master Node |
| **seatunnel-worker-1** | internal | Apache SeaTunnel Execution Worker Node |

---

## 🛠️ How to Start the Cluster

Navigate to the `seatunnel/` directory and run:

```bash
docker compose up -d
```

Check status:

```bash
docker compose ps
```

---

## 🔗 Integration with Schema Evolution Core

- **Schema Evolution Engine**: Monitors source changes and executes DDL operations (`ALTER TABLE ... ADD COLUMN ...`) on StarRocks / Data Warehouse Target.
- **Apache SeaTunnel**: High-throughput distributed data ingestion engine sinking Kafka messages into StarRocks.
