# Perpetua Goal Generator Checkpoints

## PGG-003 - 2026-01-12T22:30:00+08:00

**Summary:** Simplified uploader - 230 non-branded goals created

**Goal:** Create simplified non-branded goals (1 campaign per ASIN instead of 12), combining all match types

**Status:** Complete

**Changes:**
1. Created `extract_unbranded.py` - extracts unbranded keywords from bulk export
2. Created `perpetua-simplified-uploader.js` - creates 1 goal per ASIN with all match types
3. Created `run_harvesting.js` - creates goals for ASINs without existing keywords
4. Trimmed 710MB bulk export to 578MB for 236 target ASINs
5. Extracted 7,376 unbranded keywords across 207 ASINs
6. Identified 29 ASINs without unbranded keywords
7. Successfully uploaded 207 goals with keywords + 23 harvesting-only goals

**Files modified:**
1. extract_unbranded.py (new) - keyword extraction from bulk export
2. perpetua-simplified-uploader.js (new) - main uploader script
3. run_harvesting.js (new) - harvesting-only goals uploader
4. unbranded_keywords.json (new) - extracted keywords for 207 ASINs
5. harvesting_only_keywords.json (new) - 29 ASINs with seed keywords
6. asins_without_unbranded_keywords.txt (new) - list of 29 ASINs
7. simplified_upload_progress.json (new) - progress tracking
8. harvesting_upload_progress.json (new) - harvesting progress tracking
9. product_cache.json (updated) - ASIN to product_id mapping

**Commits:**
1. (pending) - All changes not yet committed

**Key decisions:**
1. **1 campaign per ASIN** - Simplified from 12 campaigns (branded, competitor, PAT, auto, etc.) to just 1 non-branded campaign with all match types combined
2. **Naming convention: `SKU -JN[SP_NON-BRANDED]`** - User specified this format (removed ASIN from name)
3. **Extract ASIN from campaign name** - Bulk export ASIN column was empty, had to parse ASIN from campaign name using regex `\b(B[0-9A-Z]{9})\b`
4. **Include all keyword states** - Removed paused/archived filter to capture all historical keywords
5. **Harvesting goals need seed keyword** - Perpetua API requires at least 1 keyword, used "nightstand"/"sideboard" as broad seed based on SKU prefix (NT/SD)
6. **6 ASINs not in Perpetua catalog** - B00XHKC1WK, B01G4G72AO, B08467WS27, B08Z1C52LG, B0C3WP79BH, B0C5JV2G69 - skipped

**Upload stats:**
- Goals with keywords: 207 (from bulk export)
- Harvesting-only goals: 23 (with seed keyword)
- Total goals created: 230
- Products not found: 6
- Budget: $50/day, ACOS: 60%

**Blockers:** None

**Next steps:**
1. Commit changes to git
2. Monitor goal performance in Perpetua
3. Consider adding the 6 missing products to Perpetua catalog

---

## PGG-002 - 2026-01-10T13:15:00+08:00

**Summary:** Ran first batch upload - hit Perpetua account goal limit

**Goal:** Upload all 1265 goals to Perpetua via API

**Status:** Partial - 488 goals created, hit account limit

**What changed:**
1. Ran full batch upload using `perpetua-api-uploader.js`
2. Successfully created 488 goals (86 unique ASINs)
3. Hit Perpetua account limit: "Account cannot create any more custom goals"
4. Created `processed_asins.txt` - list of 86 ASINs uploaded
5. Created `remaining_asins.txt` - list of 150 ASINs pending

**Upload stats:**
- Goals created: 488 / 1265
- ASINs completed: 86
- ASINs remaining: 150
- Last successful row: 487

**Blockers:**
- Perpetua account has reached max custom goals limit
- Need to contact Perpetua sales to increase limit

**Next steps:**
1. Contact Perpetua sales to increase goal limit
2. Resume upload with `node perpetua-api-uploader.js` (auto-resumes from row 488)
3. Or delete old/unused goals in Perpetua to free up slots

---

## PGG-001 - 2026-01-10T12:30:00+08:00

**Summary:** Added direct API uploader for Perpetua goals

**Goal:** Replace unreliable browser automation with direct API calls for creating Perpetua goals

**Status:** Complete

**Changes:**
1. Created `perpetua-api-uploader.js` - Direct API script for goal creation
2. Added GraphQL product search to get product_id from ASIN
3. Added support for keyword campaigns with proper match types (EXACT, PHRASE, BROAD)
4. Added support for PAT campaigns with TARGETING_EXPRESSION match type
5. Added negative keywords (exact + phrase) support
6. Added negative ASINs support for PAT campaigns
7. Added keyword harvesting settings:
   - BRANDED campaigns: MANUALLY_APPROVE (requires approval)
   - COMPETITOR/MANUAL campaigns: AUTOMATICALLY_ADD (auto-harvests)
8. Added progress tracking with resume capability
9. Added product ID caching for performance
10. Auto-skips unavailable products and continues

**Files modified:**
1. perpetua-api-uploader.js (new)
2. package.json (added api scripts)
3. perpetua-uploader.js (browser automation improvements - not used)

**Key decisions:**
1. Direct API is faster and more reliable than browser automation
2. GraphQL used for product search (apollo.perpetua.io)
3. REST API used for goal creation (crispy.perpetua.io)
4. PAT targets use `keyword_text` with `match_type: TARGETING_EXPRESSION`
5. Negative ASINs also use TARGETING_EXPRESSION in negative_keyword_overrides
6. BRANDED campaigns use MANUALLY_APPROVE to prevent non-branded contamination
7. Auth token needs manual refresh from DevTools when expired

**API Endpoints discovered:**
1. Product search: `POST https://apollo.perpetua.io/` (GraphQL)
2. Goal creation: `POST https://crispy.perpetua.io/engine/v3/geo_companies/{id}/uni_goals/MULTI_AD_GROUP_CUSTOM_GOAL/`

**Blockers:** None

**Next steps:**
1. Monitor full batch upload (1265 goals)
2. Consider adding batch retry for failed goals
3. Add token refresh automation if needed

---
