# Apache SeaTunnel Stack Integration

This folder contains the Docker Compose infrastructure setup for **Apache SeaTunnel 2.3.13** cluster (Master & Worker).

## 🚀 Services Overview

| Service | Host Port | Role / Description |
| :--- | :--- | :--- |
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

- **Schema Evolution Engine**: Monitors source changes and executes DDL operations (`ALTER TABLE ... ADD COLUMN ...`) on Data Warehouse Target.
- **Apache SeaTunnel**: High-throughput distributed data ingestion engine sinking Kafka messages into Target Warehouse.
