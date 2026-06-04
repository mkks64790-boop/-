# Stage60A Dependency Inventory and Facade Boundary Review Handoff

**Use this as the task-specific handoff. Always start with the master memory snapshot.**

## 1. Master Memory Snapshot (MUST READ FIRST - Non-Negotiable)
`docs/agent-md/handoff/stage-60-governance-memory-snapshot.md`

This is the canonical current state for all agents. It defines:
- Governance-only mode (no real UVR/RVC, no new milestone services, etc.).
- Next recommended task: exactly `Stage60A: dependency inventory and facade boundary review`.
- Required outputs for this stage.
- Consolidation direction (durable services: execution_safety_service, artifact_lifecycle_service, etc.).
- API preference change direction.
- Caution about working tree state (C-4b + Stage60 artifacts mixed).

**Any work on this task that does not start by reading and internalizing the memory snapshot is invalid.**

## 2. Specific Task
**Task**: Perform dependency inventory + propose facade boundaries + support user's RVC bundling requirement (main + 秋风RVC backup).

**Main Instruction Prompt** (execute this after the memory snapshot and this handoff):
`docs/agent-md/architect/stage-60a-dependency-inventory-facade-boundary-review-prompt.md`

This prompt is written to the latest template and explicitly incorporates:
- The memory snapshot's exact requirements.
- The bundling plan (`docs/governance/stage60-training-engine-bundling-plan.md`) for putting complete RVC-WebUI (primary) + 秋风RVC backup + AudioPipeline into `external/` inside the workspace.
- User's concrete situation: prepared materials ready, current external RVC/AudioPipeline uncertain/incomplete (previous local deploys by agents), desire for self-contained stable training (no deletion risk, launcher support for main + backup on 7866/7865).

## 3. Key Context from Recent Work
- Stage60 governance sprint completed (Constitution + ADRs + plans).
- Bugfix small-debt-fixes completed and reviewed (Pass). Included cleanup for bundling paths (vocal_separator import order) and self-check separation of code vs external runtime (directly helpful for RVC env issues).
- Current tree has pre-existing C-4b code + Stage60 docs + bundling prep changes (path updates in voice_changer/model_trainer/vocal_separator, launcher support for backup, .gitignore, setup script, the bundling plan itself).
- "秋风RVC" is a specific RVC model the user has enabled as backup in the studio (registered via import-rvc or scan, likely using the secondary port/instance via RVC_FALLBACK_BASES in voice_changer.py and svc_fallback in engine_manager).

## 4. Scope Reminder
- Inventory + proposal only.
- No feature code.
- No real execution.
- Support the bundling as part of the inventory (analyze current engine paths, propose how external/rvc-webui + external/rvc-webui-backup will work with existing model registration, studio track voice_model selection, launcher, etc.).
- Output must enable safe follow-up (Stage60B facade implementation).

## 5. Deliverables
- Full worker report at `docs/agent-md/worker/stage-60a-dependency-inventory-facade-boundary-review-report.md` (follow worker-report-template exactly, with governance sections).
- Supporting artifacts as specified in the prompt (dependency graph, interface freeze list, facade boundary proposals, exact test migration gate list, bundling integration details for main + 秋风 backup).

## 6. After Completion
- Do not commit.
- Share the full worker report + any graphs/proposals + `git status --porcelain` + `git diff --stat` with the coordinator (human) / Grok.
- Grok will review (governance style), then we will refine into the final Stage60A execution plan if needed.

## 7. Alignment
This task directly executes the memory snapshot's "Next Recommended Task".
It also advances the user's goal of stable, workspace-integrated training engines (main RVC + 秋风RVC backup) so prepared materials can be used reliably.

Human coordinator will provide the memory snapshot + this handoff + the Stage60A prompt to the executing agent (GPT or other).

---
*Prepared after the bugfix review and in response to the user's need for clear handover instructions for the GPT side.*