# Tower Operating Preferences

## Project Purpose

spear is for building and setting up a simulator for active illumination research.

## Default Operating Style

- Tower's main value is memory/context savings and concise orchestration, not heavyweight multi-agent workflow.
- Default flow: quick discussion with the user, Builder implements, then the user runs the simulator to check behavior.
- Builder should be the normal implementation route for code changes.
- Inspector should almost never be sent by default. Use Inspector only when the user asks for review/QA or a high-risk change warrants it.
- Scout is for research during deep technical discussions, not routine implementation.
