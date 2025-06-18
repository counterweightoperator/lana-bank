# Rollup generator

Rough reqs:
* Given a description containing:
  + A set of events with their schemas
  + A definition of a target table where you roll those events up
  + Some description of how each event modifies the target table
* Generate
  + Postgres-compatible SQL to:
    - Create the target table
    - Use triggers and functions to read events from some event stream table and update the target table atomically
