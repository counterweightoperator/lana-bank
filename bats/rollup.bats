#!/usr/bin/env bats

load "helpers"

setup_file() {
  start_server
  login_superadmin
}

teardown_file() {
  stop_server
}

@test "Pablo's rollup creates expected state" {

  ### Run user errands so we have events to rollup
  bank_manager_email=$(generate_email)
  customer_email=$(generate_email)
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


  ### Now we actually check that we rolled things up the right way
  run_query() {
    psql postgres://user:password@localhost:5433/pg -t -A -c "$1" | xargs
  }

  check_count() {
    local query="$1"
    local expected="$2"
    [ "$(run_query "$query")" == "$expected" ] && echo "true" || echo "false"
  }

  bank_manager_is_there=$(check_count "select count(*) from users where email='${bank_manager_email}';" 1)
  customer_is_there=$(check_count "select count(*) from users where email LIKE '%example.com';" 1)
  both_have_authentication_id=$(check_count "select count(*) from users where authentication_id IS NOT NULL;" 2)
  both_have_roles=$(check_count "select count(*) from users where role_id IS NOT NULL;" 2)
  both_have_received_an_update=$(check_count "select count(*) from users where created_at != updated_at;" 2)

  [[ "$bank_manager_is_there" == "true" ]] || exit 1
  [[ "$customer_is_there" == "true" ]] || exit 1
  [[ "$both_have_authentication_id" == "true" ]] || exit 1
  [[ "$both_have_roles" == "true" ]] || exit 1
  [[ "$both_have_received_an_update" == "true" ]] || exit 1
}