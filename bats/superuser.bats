#!/usr/bin/env bats

load "helpers"

setup_file() {
  start_server
  login_superadmin
  
  export bank_manager_email=$(generate_email)
  export customer_email=$(generate_email)
}

teardown_file() {
  stop_server
}

@test "superuser: can create bank manager" {
  variables=$(
    jq -n \
    --arg email "$bank_manager_email" \
    '{
      input: {
        email: $email
        }
      }'
  )

  exec_admin_graphql 'user-create' "$variables"
  user_id=$(graphql_output .data.userCreate.user.userId)
  [[ "$user_id" != "null" ]] || exit 1

  exec_admin_graphql 'list-roles'
  role_id=$(graphql_output ".data.roles.nodes[] | select(.name == \"bank-manager\").roleId")
  [[ "$role_id" != "null" ]] || exit 1

  variables=$(
    jq -n \
    --arg userId "$user_id" --arg roleId "$role_id" \
    '{
      input: {
        id: $userId,
        roleId: $roleId
        }
      }'
  )

  exec_admin_graphql 'user-update-role' "$variables"
  role=$(graphql_output .data.userUpdateRole.user.role.name)
  [[ "$role" = "bank-manager" ]] || exit 1
}


@test "superuser: can create customer" {
  telegramId=$(generate_email)
  customer_type="INDIVIDUAL"

  variables=$(
    jq -n \
    --arg email "$customer_email" \
    --arg telegramId "$telegramId" \
    --arg customerType "$customer_type" \
    '{
      input: {
        email: $email,
        telegramId: $telegramId,
        customerType: $customerType
      }
    }'
  )

  exec_admin_graphql 'customer-create' "$variables"
  customer_id=$(graphql_output .data.customerCreate.customer.customerId)
  [[ "$customer_id" != "null" ]] || exit 1
}

@test "Pablo's rollup materializes user creation" {
  bank_manager_is_there=$(psql postgres://user:password@localhost:5433/pg -t -A -c "select count(*) from users where email='${bank_manager_email}';" | xargs)
  customer_is_there=$(psql postgres://user:password@localhost:5433/pg -t -A -c "select count(*) from users where email LIKE '%example.com';" | xargs)
  echo "$customer_is_there"
  [[ "$bank_manager_is_there" == "1" ]] || exit 1
  [[ "$customer_is_there" == "1" ]] || exit 1
}