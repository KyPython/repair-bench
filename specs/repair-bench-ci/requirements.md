# Requirements: repair-bench CI wiring

Spec ID: RBC · Issue: #6 · Status: proposed; Ky approves by merging this spec-only PR

## Introduction

The benchmark has node and python suites but no test script, so CI runs
nothing. This spec wires the environment-independent node suites into the
default test command and documents the browser-dependent python suites
separately until they get skip guards.

## Requirements

### Requirement 1: Default test command (RBC-1)

**User Story:** As Ky, I want CI to run the benchmark suites, so that a
green gate means tested code.

#### Acceptance Criteria

1. RBC-1.1 WHEN the gate runs test THEN the root package.json SHALL run
   the node suites and the submission syntax check.
2. RBC-1.2 WHEN browsers are available THEN the test:python script SHALL
   run the a11y-lab and submission python suites.
