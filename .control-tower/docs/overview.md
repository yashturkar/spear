# Control Tower Overview

This project uses Control Tower as a persistent orchestration layer over Codex CLI.

Tower is the user-facing coordinator. Builder, Inspector, Scout, Git-master, and Scribe are specialist subagents invoked through typed packets.

## Project Purpose

spear is for building and setting up a simulator for active illumination research.

## Operating Preferences

- Tower's main value is memory/context savings and concise orchestration, not heavyweight multi-agent workflow.
- Default flow: quick discussion with the user, Builder implements, then the user runs the simulator to check behavior.
- Inspector should almost never be sent by default. Use only when the user asks for review/QA or a high-risk change warrants it.
- Scout is for research during deep technical discussions, not routine implementation.
- Durable preference source: `docs/tower_operating_preferences.md`.
