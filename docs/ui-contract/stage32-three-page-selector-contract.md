# Stage 32 Three-Page Selector Contract

This contract protects the product shell selectors used by Dashboard, Factory, Studio, and their smoke tests. Future UI work may rearrange layout and visual hierarchy, but these anchors should not be renamed or removed without updating the dependent tests and this contract in the same change.

## Rules

- Keep stable IDs and `data-*` anchors when changing markup.
- Dynamic selectors may be rendered only when matching data exists, but the rendering code must preserve the same selector names.
- Default noisy or technical sections stay collapsed on first load.
- Dashboard, Factory, and Studio must all keep the shared top navigation: `/`, `/factory`, `/studio`.
- Desktop and mobile viewports must not introduce horizontal page scroll.

## Dashboard Selectors

| Selector | Purpose | Depended On By | Rename Allowed |
| --- | --- | --- | --- |
| `#taskCenter` | Main job center panel | Stage 17, Stage 32B, Stage 32A smoke | No |
| `#entryCenter` | Cover/train creation entry panel | Stage 17, Stage 32B, Stage 32A smoke | No |
| `#modelPanel` | Model asset side panel | Stage 17, Stage 32B, Stage 32A smoke | No |
| `#diagnosticsPanel` | Diagnostics side panel | Stage 17, Stage 32B, Stage 32A smoke | No |
| `#coverModelSelect` | Cover model selector | Dashboard creation flow smoke | No |
| `#jobsTableBody` | Job table body | Dashboard job selection smoke | No |
| `.job-row[data-job-id]` | Dynamic job row anchor | Dashboard job detail and Studio jump smoke | No |
| `#jobSummaryCard` | Productized job summary | Stage 19/32 smoke | No |
| `#jobActionBar` | Job action area | Retry/requeue/cancel/download/Studio smoke | No |
| `[data-open-studio="true"]` | Completed cover job Studio action | Stage 17 and closure smoke | No |
| `#jobStageLogsBody` | Stage log drawer body | Stage 19/32 default-collapse smoke | No |
| `#jobTechnicalBody` | Job technical detail drawer body | Stage 19/32 default-collapse smoke | No |
| `#modelsInventoryBody` | Model inventory drawer body | Stage 18/32 default-collapse smoke | No |
| `#modelsInventoryToggleBtn` | Model inventory drawer toggle | Stage 18/32 smoke | No |
| `#modelsList [data-model-id]` | Dynamic model list item anchor | Model selection smoke | No |
| `#modelDetailCard` | Selected model detail card | Stage 19/32 smoke | No |
| `#modelUseForCoverBtn` | Use selected model for cover | Dashboard model action smoke | No |
| `#modelSourceJobBtn` | Open source training job | Stage 27/28 linkage smoke | No |
| `#modelTechnicalBody` | Model technical detail drawer body | Stage 19/32 default-collapse smoke | No |
| `[data-mobile-tab-target]` | Mobile tab switch anchor | Stage 16/32 mobile smoke | No |

Default collapsed Dashboard sections:

- `#jobStageLogsBody`
- `#jobTechnicalBody`
- `#modelsInventoryBody`
- `#modelTechnicalBody`
- `#diagnostics-detail-panel`

## Factory Selectors

| Selector | Purpose | Depended On By | Rename Allowed |
| --- | --- | --- | --- |
| `#factoryCreateBatchForm` | Batch creation form | Factory smoke | No |
| `#factoryImportTracksForm` | Track import form | Factory smoke | No |
| `#factoryRefreshBtn` | Factory refresh action | Factory smoke | No |
| `#factoryBatchesList` | Batch list container | Factory smoke | No |
| `#factoryTracksList` | Track list container | Factory smoke | No |
| `#factoryCoverModelSelect` | Model selector for cover job | Factory-to-cover smoke | No |
| `#factoryCreateCoverJobBtn` | Create cover job CTA | Factory-to-cover smoke | No |
| `#factoryTrackJobsList` | Related jobs drawer list | Factory job bridge smoke | No |
| `#factoryTrackOutcomeCard` | Latest completed outcome card | Stage 23/28 smoke | No |
| `#factoryCurrentMasterCard` | Current master card | Stage 25/28 smoke | No |
| `#factoryTrackTitle` | Current track title | Factory smoke | No |
| `#factoryTrackSubtitle` | Current track subtitle | Factory smoke | No |
| `#factoryLyricText` | Lyric document editor | Factory lyric smoke | No |
| `#factoryLyricsToggleBtn` | Lyrics drawer toggle | Stage 32 smoke | No |
| `#factoryLyricsBody` | Lyrics drawer body | Stage 32 default-collapse smoke | No |
| `[data-batch-id]` | Dynamic batch item anchor | Factory smoke | No |
| `[data-track-id]` | Dynamic track item anchor | Factory smoke | No |
| `[data-track-job-id]` | Dynamic related job anchor | Factory job bridge smoke | No |
| `[data-studio-url]` | Open Studio action | Factory-to-Studio smoke | No |
| `[data-download-url]` | Download final artifact action | Factory and closure smoke | No |

Default collapsed Factory sections:

- `#factoryLyricsBody`
- `#factoryJobsBody`

## Studio Selectors

| Selector | Purpose | Depended On By | Rename Allowed |
| --- | --- | --- | --- |
| `#studioSourceContextCard` | Factory/track/source context | Stage 23/28/30B smoke | No |
| `#studioSourceMetaGrid` | Context metadata grid | Stage 23/30B smoke | No |
| `#studioFactoryBackBtn` | Return to Factory context | Stage 23/30B smoke | No |
| `#studioArtifactSummaryCard` | Current artifact summary | Stage 17/30B smoke | No |
| `#studioSummaryDownloadBtn` | Download current artifact | Stage 17/28/30B smoke | No |
| `#studioTrackHistoryPanel` | Track history panel shell | Stage 24B/32 smoke | No |
| `#studioTrackHistoryList` | Track history list | Stage 24B/28 smoke | No |
| `[data-track-history-job-id]` | Dynamic track history item | Stage 24B smoke | No |
| `[data-set-track-master-job-id]` | Set current master action | Stage 25/28 smoke | No |
| `#studioEffectRackList` | Effect Rack shell | Stage 30B/32 smoke | No |
| `[data-effect-slot-toggle]` | Effect slot toggle | Stage 30B smoke | No |
| `#studioTechnicalToggleBtn` | Technical drawer toggle | Stage 30B/32 smoke | No |
| `#studioTechnicalBody` | Technical drawer body | Stage 30B/32 default-collapse smoke | No |

Default collapsed Studio sections:

- `#studioTechnicalBody`
- `#studioTrackHistoryBody`
- `#studioLibraryBody`

## Guard Scripts

- `frontend\playwright_stage32b_three_page_layout_smoke.cjs` verifies the normalized three-page layout.
- `frontend\playwright_stage32a_ui_contract_guard_smoke.cjs` verifies the selector contract, default collapsed state, core CTA presence, and desktop/mobile horizontal-scroll guard.
- Existing related smoke scripts must continue to pass: Stage 17 Dashboard/Studio, Factory smoke, Stage 30B Studio shell, and optional closure/linkage smoke scripts when the local environment is available.
