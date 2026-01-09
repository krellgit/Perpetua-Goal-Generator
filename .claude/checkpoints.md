# Perpetua-Goal-Generator Checkpoints

## 2026-01-10T03:25:43

**Goal:** Create Playwright browser automation script to upload 1,265 goals to Perpetua via UI (no API available)

**Current status:** In progress. Script runs but has issues with some UI element interactions.

**What changed:**
1. Created `perpetua-uploader.js` - Playwright automation script
2. Created `package.json` with Playwright and csv-parse dependencies
3. Updated README with browser automation setup instructions
4. Script successfully: logs in, navigates to Goals, clicks New Goal, fills goal name, clicks Custom, searches ASIN
5. Script has issues with: clicking "Select" for ASIN (sometimes works), match type checkboxes, harvesting toggle

**Files created/modified:**
1. `perpetua-uploader.js` - Main automation script
2. `package.json` - Node.js dependencies
3. `README.md` - Added browser automation section

**Key features implemented:**
1. Preset credentials in CONFIG
2. --start-row and --limit CLI args for testing
3. --dry-run mode
4. Progress saving to upload_progress.json
5. Resume capability

**Blockers:**
1. Harvesting toggle click causes page to reset (skipped for now)
2. Match type checkbox toggling needs testing
3. "Select" button for ASIN selection inconsistent

**Next steps:**
1. Test match type selection with current click-on-label approach
2. Verify "Add Keyword Targets" button click works
3. Verify "Launch Goal" button click works
4. If goal creation works, re-enable harvesting and negatives one at a time
5. Run on full dataset once stable

---

## 2026-01-10T12:45:00

**Goal:** Fix branded keywords in agent_task_list.csv - branded campaigns only had "nature trut" as a single keyword instead of multiple branded keyword variations.

**Current status:** Completed. Agent task list regenerated with correct branded keywords.

**What changed:**
1. Investigated branded keyword issue - discovered source Amazon bulk export only contained "nature trut" as positive branded keyword
2. Found branded keywords were stored as negative keywords in Competitor campaigns (to exclude branded terms from competitor targeting)
3. Extracted 9 branded keywords from competitor negatives
4. Removed "naturesfortune" and "truth" per user request
5. Regenerated agent_task_list.csv with 7 branded keywords for all branded campaigns

**Branded keywords now used:**
1. nature trut
2. nature truth
3. nature's truth
4. natures truth
5. nature's reward
6. naturesreward
7. naturestruth

**Blockers:** None

**Next steps:**
1. User to test the agent_task_list.csv with their automation agent
2. If Perpetua CSV upload is needed later, may need to revisit the format issues (MAG_AdGroup_MANUAL invalid type, keywords on wrong row level)

---
