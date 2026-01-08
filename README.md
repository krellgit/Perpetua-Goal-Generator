# Perpetua Goal Generator

A tool for generating CSV files for Perpetua's bulk operations to launch and edit Custom (Single-Campaign) Goals.

## Overview

This tool helps create properly formatted CSV files for Perpetua's bulk upload feature, supporting:

1. **Keyword Targeting Goals** (`SingleCampaign_KW`)
2. **Product Attributed Targeting Goals** (`SingleCampaign_PAT`)

## Naming Convention

All goals follow the naming pattern:
```
SKU - ASIN [SP_SEGMENT_MATCHTYPE] JN
```

Examples:
1. `NT15511A - B07Y5L9WLP [SP_KEYWORD_EXACT] JN`
2. `NT15511A - B07Y5L9WLP [SP_KEYWORD_PHRASE] JN`
3. `NT15511A - B07Y5L9WLP [SP_KEYWORD_BROAD] JN`
4. `NT15511A - B07Y5L9WLP [SP_PAT_ASIN] JN`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Generate Empty Template

Generate a Perpetua CSV template with your ASINs/SKUs (no keywords):

```bash
python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv
```

### Generate with Keywords from Amazon Export

1. Export your campaigns from Amazon Ads Console:
   1.1. Go to Amazon Advertising Console
   1.2. Navigate to Sponsored Products > Bulk Operations
   1.3. Click "Create spreadsheet for download"
   1.4. Select your campaigns and download

2. Run the generator with the export:

```bash
python main.py generate --asin-sku "ASIN and SKU.csv" --amazon-export bulk.xlsx --output goals.csv
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
| `--kw-only` | - | Generate only keyword goals |
| `--pat-only` | - | Generate only PAT goals |
| `--combined` | - | Combine match types into single goal |

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

1. Goal rows for each ASIN (KW and/or PAT)
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

## Reference

Based on [Perpetua Bulk Operations Documentation](https://help.perpetua.io/en/articles/7956795-bulk-operations-launch-edit-your-goals-segments#h_94297ee066)
