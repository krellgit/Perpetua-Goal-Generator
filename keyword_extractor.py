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
    """Keywords and targets extracted for a campaign/ASIN."""
    asin: str
    sku: str
    exact_keywords: List[str] = field(default_factory=list)
    phrase_keywords: List[str] = field(default_factory=list)
    broad_keywords: List[str] = field(default_factory=list)
    pat_targets: List[str] = field(default_factory=list)
    negative_exact: List[str] = field(default_factory=list)
    negative_phrase: List[str] = field(default_factory=list)


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
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    # Normalize column names (Amazon exports can vary)
    df.columns = df.columns.str.strip().str.lower()

    # Initialize results for all ASINs
    results: Dict[str, CampaignKeywords] = {}
    for asin, sku in asin_sku_map.items():
        results[asin] = CampaignKeywords(asin=asin, sku=sku)

    # Common column name variations
    keyword_cols = ['keyword', 'keyword text', 'keyword or product targeting']
    match_type_cols = ['match type', 'matchtype', 'keyword match type']
    asin_cols = ['asin', 'advertised asin', 'product asin', 'sku']
    campaign_cols = ['campaign name', 'campaign']
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

                if 'negative' in match_type:
                    if 'exact' in match_type:
                        campaign_kw.negative_exact.append(keyword)
                    else:
                        campaign_kw.negative_phrase.append(keyword)
                elif 'exact' in match_type:
                    campaign_kw.exact_keywords.append(keyword)
                elif 'phrase' in match_type:
                    campaign_kw.phrase_keywords.append(keyword)
                elif 'broad' in match_type:
                    campaign_kw.broad_keywords.append(keyword)

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
                    results[associated_asin].pat_targets.extend(asin_matches)

    # Deduplicate all lists
    for asin, kw in results.items():
        kw.exact_keywords = list(dict.fromkeys(kw.exact_keywords))
        kw.phrase_keywords = list(dict.fromkeys(kw.phrase_keywords))
        kw.broad_keywords = list(dict.fromkeys(kw.broad_keywords))
        kw.pat_targets = list(dict.fromkeys(kw.pat_targets))
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
        total = (len(kw.exact_keywords) + len(kw.phrase_keywords) +
                 len(kw.broad_keywords) + len(kw.pat_targets))
        if total > 0:
            print(f"{kw.sku} ({asin}): {total} keywords/targets")
