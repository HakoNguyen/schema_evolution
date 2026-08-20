# Apache SeaTunnel Stack Integration

This folder contains the Docker Compose infrastructure setup for **Apache SeaTunnel 2.3.13** cluster (Master & Worker).

## 🚀 Services Overview

| Service | Host Port | Role / Description |
| :--- | :--- | :--- |
| **seatunnel-master** | `8080`, `5801` | **Apache SeaTunnel Cluster Master Node & Built-in Web Console** (`http://localhost:8080`) |
| **seatunnel-worker-1** | internal | Apache SeaTunnel Execution Worker Node |

---

## 🛠️ How to Start the Cluster

Navigate to the `seatunnel/` directory and run:

```bash
docker compose up -d
```

Access the **SeaTunnel Built-in Web Console & REST API** at:
👉 **`http://localhost:8080`**

Check status:

```bash
docker compose ps
```

---

## 🔗 Integration with Schema Evolution Core

- **Schema Evolution Engine**: Monitors source changes and executes DDL operations (`ALTER TABLE ... ADD COLUMN ...`) on Data Warehouse Target.
- **Apache SeaTunnel**: Distributed data ingestion engine sinking Kafka messages into Target Warehouse.
