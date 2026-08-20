# Debezium Connector Registration Script

$debeziumUrl = "http://localhost:8083/connectors"

# Fetch existing connector names
try {
    $existingList = Invoke-RestMethod -Uri $debeziumUrl -Method Get
} catch {
    Write-Error "Failed to connect to Debezium Connect API at $debeziumUrl. Make sure Debezium is running."
    exit 1
}

# 1. Register MySQL Connector (mysql_self_monitor)
$mysqlPayload = @{
    name = "mysql-source-connector"
    config = @{
        "connector.class" = "io.debezium.connector.mysql.MySqlConnector"
        "tasks.max" = "1"
        "database.hostname" = "mysql_db"
        "database.port" = "3306"
        "database.user" = "root"
        "database.password" = "password123"
        "database.server.id" = "184054"
        "topic.prefix" = "mysql_self_monitor"
        "schema.history.internal.kafka.bootstrap.servers" = "redpanda:9092"
        "schema.history.internal.kafka.topic" = "schema-changes.mysql_self_monitor"
        "include.schema.changes" = "true"
        "database.include.list" = "sample_db"
    }
} | ConvertTo-Json -Depth 5

Write-Host "Registering MySQL Source Connector..."
try {
    if ($existingList -contains "mysql-source-connector") {
        Write-Host "MySQL connector already exists. Re-creating..."
        Invoke-RestMethod -Uri "$debeziumUrl/mysql-source-connector" -Method Delete | Out-Null
        Start-Sleep -Seconds 2
    }
    $response = Invoke-RestMethod -Uri $debeziumUrl -Method Post -Body $mysqlPayload -ContentType "application/json"
    Write-Host "MySQL connector registered successfully!"
} catch {
    Write-Error "Failed to register MySQL connector: $_"
}

# 2. Register Postgres Connector (pg_to_mysql)
$postgresPayload = @{
    name = "postgres-source-connector"
    config = @{
        "connector.class" = "io.debezium.connector.postgresql.PostgresConnector"
        "tasks.max" = "1"
        "database.hostname" = "postgres_db"
        "database.port" = "5432"
        "database.user" = "admin"
        "database.password" = "password123"
        "database.dbname" = "sample_db"
        "topic.prefix" = "pg_to_mysql"
        "plugin.name" = "pgoutput"
        "database.history.kafka.bootstrap.servers" = "redpanda:9092"
        "database.history.kafka.topic" = "schema-changes.pg_to_mysql"
    }
} | ConvertTo-Json -Depth 5

Write-Host "Registering Postgres Source Connector..."
try {
    if ($existingList -contains "postgres-source-connector") {
        Write-Host "Postgres connector already exists. Re-creating..."
        Invoke-RestMethod -Uri "$debeziumUrl/postgres-source-connector" -Method Delete | Out-Null
        Start-Sleep -Seconds 2
    }
    $response = Invoke-RestMethod -Uri $debeziumUrl -Method Post -Body $postgresPayload -ContentType "application/json"
    Write-Host "Postgres connector registered successfully!"
} catch {
    Write-Error "Failed to register Postgres connector: $_"
}

# 3. Register MongoDB Connector (mongo_to_clickhouse)
$mongoPayload = Get-Content -Raw -Path "$PSScriptRoot\mongo-source-connector.json"

Write-Host "Registering MongoDB Source Connector..."
try {
    if ($existingList -contains "mongo-source-connector") {
        Write-Host "MongoDB connector already exists. Re-creating..."
        Invoke-RestMethod -Uri "$debeziumUrl/mongo-source-connector" -Method Delete | Out-Null
        Start-Sleep -Seconds 2
    }
    $response = Invoke-RestMethod -Uri $debeziumUrl -Method Post -Body $mongoPayload -ContentType "application/json"
    Write-Host "MongoDB connector registered successfully!"
} catch {
    Write-Error "Failed to register MongoDB connector: $_"
}

