# Tower Operating Preferences

## Project Purpose

spear is for building and setting up a simulator for active illumination research.

## Default Operating Style

- Tower's main value is memory/context savings and concise orchestration, not heavyweight multi-agent workflow.
- Default flow: quick discussion with the user, Builder implements, then the user runs the simulator to check behavior.
- Builder should be the normal implementation route for code changes.
- Experimenter should run and monitor long local processes, including Infinigen generation, Blender/FBX export, Unreal imports, SPEAR cooking/packaging, flythrough/video jobs, and simulator runtime validation helpers.
- Tower should delegate process work to Experimenter with `tower-run create-packet experimenter ...` and `tower-run delegate experimenter --packet <path>`.
- Experimenter-run long or user-observable processes must use named `tmux` sessions and durable logs under a run directory, normally `.control-tower/runs/`, with the attach command reported back.
- Inspector should almost never be sent by default. Use Inspector only when the user asks for review/QA or a high-risk change warrants it.
- Scout is for research during deep technical discussions, not routine implementation.

## Git And Commit Policy

- Do not create commits, check-ins, or route Git-master to commit unless the user explicitly asks for a commit/check-in.
- Git-master can still inspect repository status, review diffs, and report Git risks when requested; creating a commit requires explicit user authorization.
- Git-master should treat `origin` as the user's fork (`https://github.com/yashturkar/spear`) and `upstream` as the parent repository (`https://github.com/spear-sim/spear.git`).
- Local `main` tracks `origin/main`; after the 2026-06-25 rebase onto `upstream/main`, publishing rewritten `main` to `origin` still requires explicit user approval.
