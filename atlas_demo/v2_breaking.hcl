schema "main" {}

table "users" {
  schema = schema.main
  column "id" {
    null = false
    type = int
  }
  column "email" {
    null = false
    type = varchar(100)
  }
  column "created_at" {
    null = true
    type = datetime
  }
  primary_key {
    columns = [column.id]
  }
}
