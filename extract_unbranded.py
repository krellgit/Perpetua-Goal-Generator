#!/usr/bin/env python3
"""
Extract unbranded keywords from trimmed bulk export.
Outputs: ASIN -> keywords with all match types combined.
"""

import pandas as pd
from pathlib import Path
import json
import re


def extract_asin_from_campaign(campaign_name: str) -> str:
    """Extract ASIN from campaign name (B followed by 9 alphanumeric chars)."""
    if not campaign_name:
        return None
    match = re.search(r'\b(B[0-9A-Z]{9})\b', campaign_name.upper())
    return match.group(1) if match else None


def extract_unbranded_keywords(csv_path: str, asin_sku_path: str):
    """
    Extract unbranded keywords from bulk export CSV.

    Unbranded = campaigns containing "Manual" but NOT "Branded" and NOT "Competitor"
    """
    print(f"Loading ASIN/SKU mapping from: {asin_sku_path}")
    asin_df = pd.read_csv(asin_sku_path)
    asin_sku_map = dict(zip(asin_df['ASIN'].str.strip(), asin_df['SKU'].str.strip()))
    print(f"  Found {len(asin_sku_map)} ASINs")

    print(f"\nReading trimmed bulk export: {csv_path}")
    # Read in chunks for large file
    chunk_size = 100000
    results = {asin: {'sku': sku, 'exact': [], 'phrase': [], 'broad': []}
               for asin, sku in asin_sku_map.items()}

    total_rows = 0
    matched_rows = 0

    for chunk in pd.read_csv(csv_path, chunksize=chunk_size, dtype=str, low_memory=False):
        total_rows += len(chunk)

        # Filter to keyword rows only
        if 'Entity' in chunk.columns:
            chunk = chunk[chunk['Entity'] == 'Keyword']

        for _, row in chunk.iterrows():
            campaign_name = str(row.get('Campaign Name (Informational only)', '')).upper()
            asin = str(row.get('ASIN (Informational only)', '')).strip().upper()
            keyword = str(row.get('Keyword Text', '')).strip()
            match_type = str(row.get('Match Type', '')).strip().lower()

            # Extract ASIN from campaign name if column is empty
            if not asin or asin == 'NAN' or asin not in results:
                asin = extract_asin_from_campaign(campaign_name)

            # Skip if no keyword or invalid ASIN
            if not keyword or keyword == 'nan' or not asin or asin not in results:
                continue

            # Only process Perpetua campaigns
            if 'PERPETUA' not in campaign_name:
                continue

            # UNBRANDED = Contains "Manual" but NOT "Branded" and NOT "Competitor"
            # Patterns: "SP - Manual" or "[SP_MANUAL_EXACT]" etc.
            is_manual = 'MANUAL' in campaign_name or 'SP_MANUAL' in campaign_name
            is_branded = 'BRANDED' in campaign_name
            is_competitor = 'COMPETITOR' in campaign_name

            if is_manual and not is_branded and not is_competitor:
                matched_rows += 1
                if 'exact' in match_type:
                    if keyword not in results[asin]['exact']:
                        results[asin]['exact'].append(keyword)
                elif 'phrase' in match_type:
                    if keyword not in results[asin]['phrase']:
                        results[asin]['phrase'].append(keyword)
                elif 'broad' in match_type:
                    if keyword not in results[asin]['broad']:
                        results[asin]['broad'].append(keyword)

        print(f"  Processed {total_rows:,} rows, found {matched_rows:,} unbranded keywords...")

    # Summary
    print(f"\n{'='*50}")
    print("Extraction Summary:")
    print(f"{'='*50}")

    total_exact = sum(len(r['exact']) for r in results.values())
    total_phrase = sum(len(r['phrase']) for r in results.values())
    total_broad = sum(len(r['broad']) for r in results.values())
    asins_with_kw = sum(1 for r in results.values() if r['exact'] or r['phrase'] or r['broad'])

    print(f"ASINs with unbranded keywords: {asins_with_kw} / {len(results)}")
    print(f"Total exact keywords: {total_exact:,}")
    print(f"Total phrase keywords: {total_phrase:,}")
    print(f"Total broad keywords: {total_broad:,}")
    print(f"Grand total: {total_exact + total_phrase + total_broad:,}")

    return results


def save_results(results: dict, output_path: str):
    """Save extracted keywords to JSON for inspection."""
    # Filter to only ASINs with keywords
    filtered = {asin: data for asin, data in results.items()
                if data['exact'] or data['phrase'] or data['broad']}

    with open(output_path, 'w') as f:
        json.dump(filtered, f, indent=2)
    print(f"\nSaved to: {output_path}")


if __name__ == '__main__':
    csv_path = Path(__file__).parent / 'trimmed_bulk.csv'
    asin_sku_path = Path(__file__).parent / 'ASINList.csv'
    output_path = Path(__file__).parent / 'unbranded_keywords.json'

    results = extract_unbranded_keywords(str(csv_path), str(asin_sku_path))
    save_results(results, str(output_path))
