# Perpetua Goal Generator

A tool for generating CSV files for Perpetua's bulk operations to launch and edit Custom (Single-Campaign) Goals.

## Overview

This tool helps create properly formatted CSV files for Perpetua's bulk upload feature. It generates a **10-campaign structure** per SKU, organizing keywords by segment and match type.

## 10-Campaign Structure

Each SKU gets up to 10 separate campaigns:

| # | Campaign Type | Goal Name Suffix | Description |
|---|---------------|------------------|-------------|
| 1 | Branded - Exact | `[SP_BRANDED_EXACT] JN` | Exact match branded keywords |
| 2 | Branded - Phrase | `[SP_BRANDED_PHRASE] JN` | Phrase match branded keywords |
| 3 | Branded - Broad | `[SP_BRANDED_BROAD] JN` | Broad match branded keywords |
| 4 | Branded - PAT | `[SP_BRANDED_PAT] JN` | Branded product attribute targeting |
| 5 | Unbranded - Exact | `[SP_MANUAL_EXACT] JN` | Exact match unbranded keywords |
| 6 | Unbranded - Phrase | `[SP_MANUAL_PHRASE] JN` | Phrase match unbranded keywords |
| 7 | Unbranded - Broad | `[SP_MANUAL_BROAD] JN` | Broad match unbranded keywords |
| 8 | Competitor - KW | `[SP_COMPETITOR_KW] JN` | Competitor keywords (all match types) |
| 9 | Competitor - PAT | `[SP_COMPETITOR_PAT] JN` | Competitor product targeting |
| 10 | Automatic | `[SP_AUTO] JN` | Automatic campaign keywords |

## Naming Convention

All goals follow the naming pattern:
```
SKU - ASIN [SP_SEGMENT_MATCHTYPE] JN
```

Examples:
1. `NT15511A - B07Y5L9WLP [SP_BRANDED_EXACT] JN`
2. `NT15511A - B07Y5L9WLP [SP_BRANDED_PHRASE] JN`
3. `NT15511A - B07Y5L9WLP [SP_BRANDED_BROAD] JN`
4. `NT15511A - B07Y5L9WLP [SP_BRANDED_PAT] JN`
5. `NT15511A - B07Y5L9WLP [SP_MANUAL_EXACT] JN`
6. `NT15511A - B07Y5L9WLP [SP_MANUAL_PHRASE] JN`
7. `NT15511A - B07Y5L9WLP [SP_MANUAL_BROAD] JN`
8. `NT15511A - B07Y5L9WLP [SP_COMPETITOR_KW] JN`
9. `NT15511A - B07Y5L9WLP [SP_COMPETITOR_PAT] JN`
10. `NT15511A - B07Y5L9WLP [SP_AUTO] JN`

## Installation

```bash
pip install -r requirements.txt
```

## Workflow

The recommended workflow is: **Trim -> Generate**

### Step 1: Trim Large Bulk Export (Optional)

If you have a large Amazon Ads bulk export (600-700MB), first trim it to only include your ASINs:

```bash
python main.py trim --bulk-file export.xlsx --asin-sku "ASIN and SKU.csv" --output trimmed.xlsx
```

This significantly reduces file size and processing time for the generate step.

### Step 2: Generate Perpetua CSV

Generate the Perpetua bulk upload CSV:

```bash
python main.py generate --asin-sku "ASIN and SKU.csv" --amazon-export trimmed.xlsx --output goals.csv
```

## Usage

### Trim Command

Trim large Amazon Ads bulk export files to only include rows matching your ASIN list:

```bash
python main.py trim --bulk-file export.xlsx --asin-sku "ASIN and SKU.csv" --output trimmed.xlsx
```

| Option | Required | Description |
|--------|----------|-------------|
| `--bulk-file`, `-b` | Yes | Path to bulk export file (.csv or .xlsx) |
| `--asin-sku`, `-a` | Yes | Path to ASIN/SKU CSV file |
| `--output`, `-o` | Yes | Path for trimmed output file |
| `--chunk-size` | No | Rows to process at a time (default: 50000) |

### Generate Command

#### Generate Empty Template

Generate a Perpetua CSV template with your ASINs/SKUs (no keywords):

```bash
python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv
```

#### Generate with Keywords from Amazon Export

1. Export your campaigns from Amazon Ads Console:
   1.1. Go to Amazon Advertising Console
   1.2. Navigate to Sponsored Products > Bulk Operations
   1.3. Click "Create spreadsheet for download"
   1.4. Select your campaigns and download

2. (Optional) Trim the export to your ASINs:
```bash
python main.py trim --bulk-file bulk.xlsx --asin-sku "ASIN and SKU.csv" --output trimmed.xlsx
```

3. Run the generator with the export:
```bash
python main.py generate --asin-sku "ASIN and SKU.csv" --amazon-export trimmed.xlsx --output goals.csv
```

### Configuration Options

```bash
python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv \
    --budget 15 \
    --acos 25 \
    --min-bid 0.30 \
    --max-bid 3.00 \
    --status Enabled
```

| Option | Default | Description |
|--------|---------|-------------|
| `--budget` | 10 | Daily budget |
| `--acos` | 30 | Target ACoS |
| `--min-bid` | 0.20 | Minimum bid |
| `--max-bid` | 2.00 | Maximum bid |
| `--status` | Enabled | Goal status (Enabled/Paused) |

## Segment Detection Rules

Keywords are automatically categorized based on campaign name patterns in the Amazon bulk export:

| Segment | Campaign Name Pattern | Description |
|---------|----------------------|-------------|
| Branded KW | Contains "BRANDED" (not "PAT") | Brand-related keywords |
| Branded PAT | Contains "BRANDED" and "PAT" | Brand product targeting |
| Unbranded KW | Contains "MANUAL" (not "COMPETITOR") | Generic/category keywords |
| Competitor KW | Contains "COMPETITOR" and "MANUAL" | Competitor brand keywords |
| Competitor PAT | Contains "PAT" (not "BRANDED") | Competitor product targeting |
| Auto | Contains "AUTO" | Automatic campaign terms |

## Input Files

### ASIN and SKU.csv

CSV with your product ASINs and SKUs:

```csv
ASIN,SKU,Count
B07Y5L9WLP,NT15511A,1
B07RF7P3FK,NT12780A,2
```

### Amazon Bulk Export (Optional)

Excel/CSV export from Amazon Ads Console containing:
1. Keyword data with match types
2. Product targeting expressions
3. Negative keywords

## Output

The generator creates a Perpetua-formatted CSV with:

1. Goal rows for each ASIN (up to 10 campaigns per SKU)
2. Product rows beneath each goal
3. All configuration values pre-filled

## CSV Format Reference

### Goal Type Row Columns

| Column | Field | Description |
|--------|-------|-------------|
| B | Goal Type | `SingleCampaign_KW` or `SingleCampaign_PAT` |
| D | Goal Title | Max 60 characters |
| F | Status | `Enabled` or `Paused` |
| H | Daily Budget | Whole numbers >= 1 |
| I | Target ACoS | Whole numbers >= 1 |
| M | Exact Keywords | Comma-separated (KW only) |
| N | Phrase Keywords | Comma-separated (KW only) |
| O | Broad Keywords | Comma-separated (KW only) |
| P | PAT Targets | Comma-separated (PAT only) |
| Q | Negative Exact | Comma-separated |
| R | Negative Phrase | Comma-separated |
| T | Min Bid | Decimal >= 0 |
| U | Max Bid | Decimal >= 0 |

### Product Rows

Add a "Product" row beneath each goal type row for each ASIN:
1. Column F: Status (`Enabled` or `Deleted`)

### Upload Results

After upload, check these columns:
1. Column AI: Result
2. Column AJ: Errors
3. Column AK: Warnings

## Browser Automation Uploader

For creating NEW goals (which bulk upload doesn't support), use the Playwright-based browser automation:

### Setup

```bash
# Install Node.js dependencies
npm install

# Install Chromium browser for Playwright
npm run install-browsers
```

### Usage

```bash
# Run the uploader (will prompt for credentials)
npm run upload

# Dry run - see what would be created without doing anything
npm run upload:dry

# Start from a specific row (e.g., resume after error)
node perpetua-uploader.js --start-row=100
```

### How It Works

1. Prompts for your Perpetua email and password
2. Opens a visible Chrome browser
3. Logs in to Perpetua
4. Navigates to Sponsored Products > Goals
5. For each row in `agent_task_list.csv`:
   5.1. Clicks "New Goal"
   5.2. Fills in goal title, ASIN, budget, ACOS
   5.3. Selects Keyword or PAT targeting
   5.4. Configures match types and negatives
   5.5. Creates the goal
6. Saves progress to `upload_progress.json` (can resume if interrupted)

### Features

1. **Resume capability** - If the script stops, it remembers where it left off
2. **Headed mode** - Watch the browser work so you can catch issues
3. **Error handling** - If a goal fails, you can choose to continue or stop
4. **Progress tracking** - See which goal is being processed

### Troubleshooting

If the script fails to find an element:
1. The Perpetua UI may have changed - selectors may need updating
2. Try increasing the `slowMo` value in the config (default: 100ms)
3. Check `upload_progress.json` to see which goal failed

## Reference

Based on [Perpetua Bulk Operations Documentation](https://help.perpetua.io/en/articles/7956795-bulk-operations-launch-edit-your-goals-segments#h_94297ee066)
