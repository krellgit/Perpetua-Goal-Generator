"""
Keyword Extractor for Amazon Ads Bulk Export

Extracts keywords and targets from Amazon Advertising bulk export spreadsheets
and maps them to ASINs for Perpetua goal generation.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CampaignKeywords:
    """Keywords and targets extracted for a campaign/ASIN, categorized by segment."""
    asin: str
    sku: str
    # Branded keywords (from "Branded" campaigns, not containing "PAT")
    branded_exact: List[str] = field(default_factory=list)
    branded_phrase: List[str] = field(default_factory=list)
    branded_broad: List[str] = field(default_factory=list)
    # Unbranded keywords (from "Manual" campaigns, not containing "Competitor")
    unbranded_exact: List[str] = field(default_factory=list)
    unbranded_phrase: List[str] = field(default_factory=list)
    unbranded_broad: List[str] = field(default_factory=list)
    # Competitor keywords (from "Competitor Manual" campaigns) - combined, not split by match type
    competitor_keywords: List[str] = field(default_factory=list)
    # PAT targets by segment
    branded_pat_targets: List[str] = field(default_factory=list)
    competitor_pat_targets: List[str] = field(default_factory=list)
    # Automatic campaign keywords
    auto_keywords: List[str] = field(default_factory=list)
    # Negatives (kept segment-agnostic for now)
    negative_exact: List[str] = field(default_factory=list)
    negative_phrase: List[str] = field(default_factory=list)


def detect_segment(campaign_name: str) -> str:
    """
    Detect campaign segment based on campaign name patterns.

    Args:
        campaign_name: The campaign name to analyze

    Returns:
        Segment identifier: 'branded_kw', 'branded_pat', 'unbranded_kw',
        'competitor_kw', 'competitor_pat', 'auto', or 'unknown'
    """
    name_upper = campaign_name.upper()

    # Order matters - check more specific patterns first
    if 'BRANDED' in name_upper and 'PAT' in name_upper:
        return 'branded_pat'
    elif 'BRANDED' in name_upper:
        return 'branded_kw'
    elif 'COMPETITOR' in name_upper and 'MANUAL' in name_upper:
        return 'competitor_kw'
    elif 'PAT' in name_upper:
        # Contains PAT but not Branded (already checked above)
        return 'competitor_pat'
    elif 'MANUAL' in name_upper:
        # Manual but not Competitor (already checked above)
        return 'unbranded_kw'
    elif 'AUTO' in name_upper:
        return 'auto'
    else:
        return 'unknown'


def extract_keywords_from_amazon_bulk(
    bulk_file_path: str,
    asin_sku_map: Dict[str, str]
) -> Dict[str, CampaignKeywords]:
    """
    Extract keywords from Amazon Ads bulk export file.

    Args:
        bulk_file_path: Path to the Amazon bulk export Excel/CSV file
        asin_sku_map: Dictionary mapping ASIN -> SKU

    Returns:
        Dictionary mapping ASIN -> CampaignKeywords
    """
    file_path = Path(bulk_file_path)

    if file_path.suffix.lower() in ['.xlsx', '.xls']:
        # Handle multi-sheet Excel files - combine all relevant sheets
        xl = pd.ExcelFile(file_path, engine='openpyxl')
        dfs = []
        for sheet in xl.sheet_names:
            try:
                sheet_df = pd.read_excel(file_path, sheet_name=sheet, dtype=str, engine='openpyxl')
                # Only include sheets that have keyword-related columns
                sheet_df.columns = sheet_df.columns.str.strip().str.lower()
                if 'keyword text' in sheet_df.columns or 'campaign name' in sheet_df.columns:
                    dfs.append(sheet_df)
            except Exception:
                continue
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
        else:
            df = pd.read_excel(file_path, dtype=str, engine='openpyxl')
            df.columns = df.columns.str.strip().str.lower()
    else:
        df = pd.read_csv(file_path, dtype=str)
        # Normalize column names (Amazon exports can vary)
        df.columns = df.columns.str.strip().str.lower()

    # Initialize results for all ASINs
    results: Dict[str, CampaignKeywords] = {}
    for asin, sku in asin_sku_map.items():
        results[asin] = CampaignKeywords(asin=asin, sku=sku)

    # Common column name variations
    keyword_cols = ['keyword', 'keyword text', 'keyword or product targeting']
    match_type_cols = ['match type', 'matchtype', 'keyword match type']
    asin_cols = ['asin', 'asin (informational only)', 'advertised asin', 'product asin', 'sku']
    campaign_cols = ['campaign name', 'campaign', 'name']
    target_cols = ['product targeting expression', 'targeting expression', 'target']

    # Find actual column names
    keyword_col = next((c for c in keyword_cols if c in df.columns), None)
    match_type_col = next((c for c in match_type_cols if c in df.columns), None)
    asin_col = next((c for c in asin_cols if c in df.columns), None)
    campaign_col = next((c for c in campaign_cols if c in df.columns), None)
    target_col = next((c for c in target_cols if c in df.columns), None)

    # Process keyword rows
    if keyword_col and match_type_col:
        for _, row in df.iterrows():
            keyword = str(row.get(keyword_col, '')).strip()
            match_type = str(row.get(match_type_col, '')).strip().lower()

            if not keyword or keyword == 'nan':
                continue

            # Try to find associated ASIN
            associated_asin = None
            if asin_col:
                asin_value = str(row.get(asin_col, '')).strip().upper()
                if asin_value in results:
                    associated_asin = asin_value

            # Try to find ASIN from campaign name
            if not associated_asin and campaign_col:
                campaign_name = str(row.get(campaign_col, ''))
                for asin in results.keys():
                    if asin in campaign_name:
                        associated_asin = asin
                        break

            if associated_asin:
                campaign_kw = results[associated_asin]
                campaign_name = str(row.get(campaign_col, '')) if campaign_col else ''
                segment = detect_segment(campaign_name)

                if 'negative' in match_type:
                    if 'exact' in match_type:
                        campaign_kw.negative_exact.append(keyword)
                    else:
                        campaign_kw.negative_phrase.append(keyword)
                elif segment == 'branded_kw':
                    if 'exact' in match_type:
                        campaign_kw.branded_exact.append(keyword)
                    elif 'phrase' in match_type:
                        campaign_kw.branded_phrase.append(keyword)
                    elif 'broad' in match_type:
                        campaign_kw.branded_broad.append(keyword)
                elif segment == 'unbranded_kw':
                    if 'exact' in match_type:
                        campaign_kw.unbranded_exact.append(keyword)
                    elif 'phrase' in match_type:
                        campaign_kw.unbranded_phrase.append(keyword)
                    elif 'broad' in match_type:
                        campaign_kw.unbranded_broad.append(keyword)
                elif segment == 'competitor_kw':
                    # Competitor keywords combined, not split by match type
                    campaign_kw.competitor_keywords.append(keyword)
                elif segment == 'auto':
                    campaign_kw.auto_keywords.append(keyword)

    # Process product targeting rows
    if target_col:
        for _, row in df.iterrows():
            target = str(row.get(target_col, '')).strip()

            if not target or target == 'nan':
                continue

            # Try to find associated ASIN
            associated_asin = None
            if asin_col:
                asin_value = str(row.get(asin_col, '')).strip().upper()
                if asin_value in results:
                    associated_asin = asin_value

            if not associated_asin and campaign_col:
                campaign_name = str(row.get(campaign_col, ''))
                for asin in results.keys():
                    if asin in campaign_name:
                        associated_asin = asin
                        break

            if associated_asin:
                # Extract ASIN targets (format: asin="B0XXXXXXXX")
                if 'asin=' in target.lower():
                    import re
                    asin_matches = re.findall(r'asin="?([A-Z0-9]{10})"?', target, re.IGNORECASE)
                    campaign_name = str(row.get(campaign_col, '')) if campaign_col else ''
                    segment = detect_segment(campaign_name)
                    if segment == 'branded_pat':
                        results[associated_asin].branded_pat_targets.extend(asin_matches)
                    else:
                        # Default to competitor PAT for other PAT campaigns
                        results[associated_asin].competitor_pat_targets.extend(asin_matches)

    # Deduplicate all lists
    for asin, kw in results.items():
        kw.branded_exact = list(dict.fromkeys(kw.branded_exact))
        kw.branded_phrase = list(dict.fromkeys(kw.branded_phrase))
        kw.branded_broad = list(dict.fromkeys(kw.branded_broad))
        kw.unbranded_exact = list(dict.fromkeys(kw.unbranded_exact))
        kw.unbranded_phrase = list(dict.fromkeys(kw.unbranded_phrase))
        kw.unbranded_broad = list(dict.fromkeys(kw.unbranded_broad))
        kw.competitor_keywords = list(dict.fromkeys(kw.competitor_keywords))
        kw.branded_pat_targets = list(dict.fromkeys(kw.branded_pat_targets))
        kw.competitor_pat_targets = list(dict.fromkeys(kw.competitor_pat_targets))
        kw.auto_keywords = list(dict.fromkeys(kw.auto_keywords))
        kw.negative_exact = list(dict.fromkeys(kw.negative_exact))
        kw.negative_phrase = list(dict.fromkeys(kw.negative_phrase))

    return results


def load_asin_sku_map(csv_path: str) -> Dict[str, str]:
    """Load ASIN to SKU mapping from CSV file."""
    df = pd.read_csv(csv_path)
    return dict(zip(df['ASIN'].str.strip(), df['SKU'].str.strip()))


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python keyword_extractor.py <asin_sku.csv> <amazon_bulk_export.xlsx>")
        sys.exit(1)

    asin_sku_path = sys.argv[1]
    bulk_export_path = sys.argv[2]

    asin_sku_map = load_asin_sku_map(asin_sku_path)
    print(f"Loaded {len(asin_sku_map)} ASIN/SKU pairs")

    keywords = extract_keywords_from_amazon_bulk(bulk_export_path, asin_sku_map)

    # Print summary
    for asin, kw in keywords.items():
        branded = len(kw.branded_exact) + len(kw.branded_phrase) + len(kw.branded_broad)
        unbranded = len(kw.unbranded_exact) + len(kw.unbranded_phrase) + len(kw.unbranded_broad)
        competitor = len(kw.competitor_keywords)
        pat = len(kw.branded_pat_targets) + len(kw.competitor_pat_targets)
        auto = len(kw.auto_keywords)
        total = branded + unbranded + competitor + pat + auto
        if total > 0:
            print(f"{kw.sku} ({asin}): {total} total")
            print(f"  Branded: {branded}, Unbranded: {unbranded}, Competitor: {competitor}")
            print(f"  PAT: {pat}, Auto: {auto}")
