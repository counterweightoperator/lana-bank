# Notes on solution

## Running

Run the following to seed the db with some test and print the console the output of the rolled-up table.

```
make reset-deps run-server

# Jump to a different shell when ready

bats -t bats/rollup.bats

psql postgres://user:password@localhost:5433/pg -c "\x on" -c "select * from users;"

```

## Changes

A few notes to navigate my changes:

* The current state contains two changes: 
  + A new migration at `lana/app/migrations/20250617085344_user_rollup.sql` that implements all the changes to the admin pg server.
  + A new `bats` test to check that the rollup leaves the target table in the desired state after seeding some events.
* About the migration:
  + Multiple things going on.
    - We create a simple table `Users`. Fields are both metadata and actual `user` attributes. Hopefully that table feels self-descriptive.
    - Then we create an `AFTER INSERT` trigger that acts everytime a new event lands at `core_user_events`.
    - The trigger fires function `fn_trigger_user_event`, that maps the different event `type` values to a dedicated function for each. These functions implement the actual rollup logic for each event, as in how the event modifies the state of the entity in the `user` table.
    - Functions `fn_project_user_initialized`, `fn_project_user_authentication_id_updated`, `fn_project_user_role_granted`, `fn_project_user_role_revoked` implement the business logic. They are dead simple, the most straightforward explanation is taking a look at them.
  + About the `bats` test:
    - I decided to piggyback on the `superuser.bats` tests to get the code that fires the different user events.
    - The test simply generates the same state as `superuser.bats` and then queries postgres directly to assert a few high level properties of the final state of the `User` table. 
    - I appreciate your `bats` tests generally try to keep interaction with the postgres through graphql, but I skipped that to keep the workload bearable. It would have taken me ages to carve the way through the stack to read from the `user` table and I don't feel it adds much for this test.
    - It's rather simple and naive but helps check things.

## Improvements and where to go from here

There's a few areas where my implementation could be improved:

* It doesn't validate events at all. We should decide where do we want to set boundaries and whether this kind of rollup functions should validate or sanitize the content of events, as well as what to do if there are issues. These includes both the content of events itself, as well as the sequence ordering (functions don't check if they get called respecting the sequence order or not).
* Currently, should a failure happen, the whole transaction, including the insert of the event, won't commit. That's *good*. But there's no trigger specific logging, so if the trigger/rollup functions cause the exception, we might be left wondering why the event couldn't be persisted. Again, we would need to discuss what would make sense here because I'm not fully familiar with what is the server already logging.
* Defining entity snapshot tables, triggers, what events must be reacted to, and how they impact the entity, is terribly manual. It's work, plus someone must be at the wheel paying attention to ensure it's in sync with what's defined in Rust.
* Doesn't deal with versioning of the user events, should new versions ever appear.

Opportunities to improve:
* Implement whatever input validation makes sense.
* Implement whatever logging makes sense.
* Add a replay function to rollup entities from scratch (or perhaps give ourselves the ability to replay events in certain time or sequence ranges).
* Metadata of the entity table (`created_at, updated_at, deleted_at, last_sequence`) could potentially be stored in separate table that only has audit/consistency checking purposes. Hard to tell what's the better option without more context/specific requirements.
* Extend mapping and events to not only deal with `type` but also `version` (or alternatively, recycle `type` for that purpose as well).
* Regarding generating (instead of handcrafting) all this house of cards of SQL for each entity/event stream, I think there are differnent approaches along the complexity/usefulness. From less to more:
  + Implement consistency checkers:
    - We assume SQL will be handcrafted.
    - Make some code to parse the entity table, trigger and functions and cross check consistency with rust definitions.
    - Doesn't help you build, but it helps noticing that you're screwing up when handcrafting.
    - Although it's kind of pointless if `e2e` testing of the rollup behaviour is thorough enough.
  + Generate SQL boilerplate programmatically:
    - Create entity snapshot DDL from code definitions.
      - It's funny how there is no single clear definition of what are the attributes of `core_user`. User events tell you one thing, but the code at `core/access/src/user/repo.rs` tells you another (e.g events indicate there's a `RoleId`, but the columns in `core/access/src/user/repo.rs` don't mention any role related field).
    - Create trigger and mapping functions boilerplate from `core/access/src/user/entity.rs` `UserEvent`.
    - Create event rollup functions boilerplate, but leave it up to the developer to implement the effects of the event on the rollup table.
  + Generate SQL boilerplate AND contents programmatically:
    - Extend the previous 
    - Create entity snapshot DDL from code definitions.
      - It's funny how there is no single clear definition of what are the attributes of `core_user`. User events tell you one thing, but the code at `core/access/src/user/repo.rs` tells you another (e.g events indicate there's a `RoleId`, but the columns in `core/access/src/user/repo.rs` don't mention any role related field).
    - Create trigger and mapping functions boilerplate from `core/access/src/user/entity.rs` `UserEvent`.
    - Create event rollup functions boilerplate.
    - The final (and most challenging) cherry on top bullet would be to generate the rollup functions logic. Lots of changes would be required for this, and I'm wondering if the complexity is worth it. Happy to discuss on the topic.
