"""
Keyword Extractor for Amazon Ads Bulk Export

Extracts keywords and targets from Amazon Advertising bulk export spreadsheets
and maps them to ASINs for Perpetua goal generation.
"""

import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


def extract_asin_from_campaign_name(campaign_name: str) -> Optional[str]:
    """Extract ASIN from campaign name (B followed by 9 alphanumeric chars)."""
    if not campaign_name or pd.isna(campaign_name):
        return None
    campaign_name = str(campaign_name)
    asin_match = re.search(r'\b(B[0-9A-Z]{9})\b', campaign_name.upper())
    if asin_match:
        return asin_match.group(1)
    return None


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
    # Competitor keywords (from "Competitor Manual" campaigns) - split by match type
    competitor_exact: List[str] = field(default_factory=list)
    competitor_phrase: List[str] = field(default_factory=list)
    competitor_broad: List[str] = field(default_factory=list)
    # PAT targets by segment
    branded_pat_targets: List[str] = field(default_factory=list)
    competitor_pat_targets: List[str] = field(default_factory=list)
    # Automatic campaign keywords
    auto_keywords: List[str] = field(default_factory=list)

    # Per-campaign negatives: Dict[campaign_key, Dict[neg_type, List[str]]]
    # campaign_key: 'branded_exact', 'branded_phrase', 'branded_broad', 'branded_pat',
    #               'unbranded_exact', 'unbranded_phrase', 'unbranded_broad',
    #               'competitor_exact', 'competitor_phrase', 'competitor_broad', 'competitor_pat',
    #               'auto'
    # neg_type: 'exact', 'phrase', 'asins'
    campaign_negatives: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    def get_negatives(self, campaign_key: str) -> Dict[str, List[str]]:
        """Get negatives for a specific campaign type."""
        if campaign_key not in self.campaign_negatives:
            self.campaign_negatives[campaign_key] = {'exact': [], 'phrase': [], 'asins': []}
        return self.campaign_negatives[campaign_key]

    def add_negative(self, campaign_key: str, neg_type: str, value: str):
        """Add a negative keyword/ASIN to a specific campaign type."""
        negs = self.get_negatives(campaign_key)
        if value not in negs[neg_type]:
            negs[neg_type].append(value)


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


def detect_campaign_key(campaign_name: str, match_type: str = None) -> str:
    """
    Detect full campaign key (segment + match type) from campaign name.

    Args:
        campaign_name: The campaign name to analyze
        match_type: Optional match type from the data row (exact/phrase/broad)

    Returns:
        Campaign key like 'branded_exact', 'unbranded_phrase', 'competitor_pat', 'auto', etc.
    """
    name_upper = campaign_name.upper()

    # Detect match type from campaign name if not provided
    if not match_type:
        if 'EXACT' in name_upper:
            match_type = 'exact'
        elif 'PHRASE' in name_upper:
            match_type = 'phrase'
        elif 'BROAD' in name_upper:
            match_type = 'broad'
        elif 'PAT' in name_upper:
            match_type = 'pat'
        else:
            match_type = 'exact'  # Default

    match_type = match_type.lower()

    # Detect segment and combine with match type
    if 'BRANDED' in name_upper and 'PAT' in name_upper:
        return 'branded_pat'
    elif 'BRANDED' in name_upper:
        return f'branded_{match_type}'
    elif 'COMPETITOR' in name_upper and 'PAT' in name_upper:
        return 'competitor_pat'
    elif 'COMPETITOR' in name_upper:
        return f'competitor_{match_type}'
    elif 'MANUAL' in name_upper:
        return f'unbranded_{match_type}'
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
    campaign_cols = ['campaign name (informational only)', 'campaign name', 'campaign', 'name']
    target_cols = ['product targeting expression', 'targeting expression', 'target']
    entity_cols = ['entity', 'entity type', 'record type']

    # Find actual column names
    keyword_col = next((c for c in keyword_cols if c in df.columns), None)
    match_type_col = next((c for c in match_type_cols if c in df.columns), None)
    asin_col = next((c for c in asin_cols if c in df.columns), None)
    campaign_col = next((c for c in campaign_cols if c in df.columns), None)
    target_col = next((c for c in target_cols if c in df.columns), None)
    entity_col = next((c for c in entity_cols if c in df.columns), None)

    # Diagnostic output
    print(f"  Available columns: {list(df.columns)[:10]}...")
    print(f"  Keyword column: {keyword_col}")
    print(f"  Match type column: {match_type_col}")
    print(f"  ASIN column: {asin_col}")
    print(f"  Campaign column: {campaign_col}")
    print(f"  Target column: {target_col}")
    print(f"  Total rows to process: {len(df):,}")

    # Track segment counts for debugging
    segment_counts = {'branded_kw': 0, 'unbranded_kw': 0, 'competitor_kw': 0,
                      'auto': 0, 'branded_pat': 0, 'competitor_pat': 0, 'unknown': 0}
    unmatched_asins = 0
    skipped_non_perpetua = 0

    # Process keyword rows
    if not keyword_col:
        print("  WARNING: No keyword column found! Keywords won't be extracted.")
    if not match_type_col:
        print("  WARNING: No match type column found! Keywords won't be extracted.")

    # Show sample campaign names for debugging
    if campaign_col and len(df) > 0:
        sample_campaigns = df[campaign_col].dropna().unique()[:5]
        print(f"  Sample campaign names: {list(sample_campaigns)}")

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
                if asin_value and asin_value != 'NAN' and asin_value in results:
                    associated_asin = asin_value

            # Try to find ASIN from campaign name if ASIN column is empty
            if not associated_asin and campaign_col:
                campaign_name = str(row.get(campaign_col, ''))
                # First try extracting ASIN pattern from campaign name
                extracted_asin = extract_asin_from_campaign_name(campaign_name)
                if extracted_asin and extracted_asin in results:
                    associated_asin = extracted_asin
                else:
                    # Fallback: check if any ASIN is substring of campaign name
                    for asin in results.keys():
                        if asin in campaign_name.upper():
                            associated_asin = asin
                            break

            if associated_asin:
                campaign_kw = results[associated_asin]
                campaign_name = str(row.get(campaign_col, '')) if campaign_col else ''

                # Only process keywords from Perpetua campaigns
                if 'PERPETUA' not in campaign_name.upper():
                    skipped_non_perpetua += 1
                    continue

                segment = detect_segment(campaign_name)
                segment_counts[segment] = segment_counts.get(segment, 0) + 1

                # Get the full campaign key for this row
                campaign_key = detect_campaign_key(campaign_name)

                if 'negative' in match_type:
                    # Store negative keywords per campaign type
                    if 'exact' in match_type:
                        campaign_kw.add_negative(campaign_key, 'exact', keyword)
                    else:
                        campaign_kw.add_negative(campaign_key, 'phrase', keyword)
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
                    # Competitor keywords split by match type
                    if 'exact' in match_type:
                        campaign_kw.competitor_exact.append(keyword)
                    elif 'phrase' in match_type:
                        campaign_kw.competitor_phrase.append(keyword)
                    elif 'broad' in match_type:
                        campaign_kw.competitor_broad.append(keyword)
                elif segment == 'auto':
                    campaign_kw.auto_keywords.append(keyword)
                # Note: 'unknown' segment keywords are not assigned to any category
            else:
                unmatched_asins += 1

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
                if asin_value and asin_value != 'NAN' and asin_value in results:
                    associated_asin = asin_value

            if not associated_asin and campaign_col:
                campaign_name = str(row.get(campaign_col, ''))
                # First try extracting ASIN pattern from campaign name
                extracted_asin = extract_asin_from_campaign_name(campaign_name)
                if extracted_asin and extracted_asin in results:
                    associated_asin = extracted_asin
                else:
                    # Fallback: check if any ASIN is substring of campaign name
                    for asin in results.keys():
                        if asin in campaign_name.upper():
                            associated_asin = asin
                            break

            if associated_asin:
                campaign_name = str(row.get(campaign_col, '')) if campaign_col else ''

                # Only process targets from Perpetua campaigns
                if 'PERPETUA' not in campaign_name.upper():
                    continue

                # Check if this is a negative product targeting row
                entity_value = str(row.get(entity_col, '')).strip().lower() if entity_col else ''
                is_negative = 'negative' in entity_value

                # Get the full campaign key for this row
                campaign_key = detect_campaign_key(campaign_name)

                # Extract ASIN targets (format: asin="B0XXXXXXXX")
                if 'asin=' in target.lower():
                    asin_matches = re.findall(r'asin="?([A-Z0-9]{10})"?', target, re.IGNORECASE)
                    if is_negative:
                        # Negative ASIN targets - store per campaign type
                        for asin_target in asin_matches:
                            results[associated_asin].add_negative(campaign_key, 'asins', asin_target)
                    else:
                        # Positive ASIN targets
                        segment = detect_segment(campaign_name)
                        if segment == 'branded_pat':
                            results[associated_asin].branded_pat_targets.extend(asin_matches)
                        else:
                            # Default to competitor PAT for other PAT campaigns
                            results[associated_asin].competitor_pat_targets.extend(asin_matches)

    # Deduplicate all keyword/target lists
    # (campaign_negatives are already deduplicated by add_negative method)
    for asin, kw in results.items():
        kw.branded_exact = list(dict.fromkeys(kw.branded_exact))
        kw.branded_phrase = list(dict.fromkeys(kw.branded_phrase))
        kw.branded_broad = list(dict.fromkeys(kw.branded_broad))
        kw.unbranded_exact = list(dict.fromkeys(kw.unbranded_exact))
        kw.unbranded_phrase = list(dict.fromkeys(kw.unbranded_phrase))
        kw.unbranded_broad = list(dict.fromkeys(kw.unbranded_broad))
        kw.competitor_exact = list(dict.fromkeys(kw.competitor_exact))
        kw.competitor_phrase = list(dict.fromkeys(kw.competitor_phrase))
        kw.competitor_broad = list(dict.fromkeys(kw.competitor_broad))
        kw.branded_pat_targets = list(dict.fromkeys(kw.branded_pat_targets))
        kw.competitor_pat_targets = list(dict.fromkeys(kw.competitor_pat_targets))
        kw.auto_keywords = list(dict.fromkeys(kw.auto_keywords))

    # Print segment detection summary
    print(f"  Segment detection results:")
    for seg, count in segment_counts.items():
        if count > 0:
            print(f"    {seg}: {count:,}")
    if unmatched_asins > 0:
        print(f"  Keywords with no matching ASIN: {unmatched_asins:,}")
    if skipped_non_perpetua > 0:
        print(f"  Skipped (non-Perpetua campaigns): {skipped_non_perpetua:,}")

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
        competitor = len(kw.competitor_exact) + len(kw.competitor_phrase) + len(kw.competitor_broad)
        pat = len(kw.branded_pat_targets) + len(kw.competitor_pat_targets)
        auto = len(kw.auto_keywords)
        total = branded + unbranded + competitor + pat + auto
        if total > 0:
            print(f"{kw.sku} ({asin}): {total} total")
            print(f"  Branded: {branded}, Unbranded: {unbranded}, Competitor: {competitor}")
            print(f"  PAT: {pat}, Auto: {auto}")
