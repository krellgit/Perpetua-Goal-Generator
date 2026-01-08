# Perpetua Goal Generator

A tool for generating CSV files for Perpetua's bulk operations to launch and edit Custom (Single-Campaign) Goals.

## Overview

This tool helps create properly formatted CSV files for Perpetua's bulk upload feature, supporting:

1. **Keyword Targeting Goals** (`SingleCampaign_KW`)
2. **Product Attributed Targeting Goals** (`SingleCampaign_PAT`)

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

## Usage

(Coming soon)

## Reference

Based on [Perpetua Bulk Operations Documentation](https://help.perpetua.io/en/articles/7956795-bulk-operations-launch-edit-your-goals-segments#h_94297ee066)
