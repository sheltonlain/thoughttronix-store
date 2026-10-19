---
name: implement
description: Implement one approved phase from a PRD and plan using feedback loops.
argument-hint: "@prd/<feature>.md @plans/<feature>.md implement phase <N>"
disable-model-invocation: true
---

# Implement

## 1. Understand the Phase

Read the referenced PRD and plan. Explore the codebase to understand the relevant files,
patterns, and conventions. If the request does not identify a phase, ask which one.

Implement only that phase. Do not begin the next one.

## 2. Implement the Phase

Run the tdd skill and follow its instructions. Implement any remaining requirements using the project's normal process. 

## 3. Run Feedback Loops

Run the test suite, linter, and formatter. Refactor the code as needed. If the tests fail, fix the issues and re-run the feedback loops until they pass.

## 4. Manual Verification

Outline the steps to manually verify that the implementation meets the requirements. Stop and ask for confirmation before proceeding to the next phase.

## 5. Finish the Phase

Update PROMPTS.md using the format specified in that file. Then commit the completed phase with a message like "Implement <feature> phase <N>". Push the commit to GitHub. 