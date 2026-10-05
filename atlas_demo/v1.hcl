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
  column "phone" {
    null = true
    type = varchar(20)
  }
  primary_key {
    columns = [column.id]
  }
}
