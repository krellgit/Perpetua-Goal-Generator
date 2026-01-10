# Perpetua Goal Generator Checkpoints

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
