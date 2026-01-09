"""
Perpetua Goal Generator

Generates CSV files for Perpetua bulk operations to launch/edit
Custom (Single-Campaign) Goals with proper naming convention.

Naming Convention: SKU - ASIN [SP_SEGMENT_MATCHTYPE] JN
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from keyword_extractor import CampaignKeywords
from progress import ProgressBar, Spinner


def load_negative_asins(file_path: str) -> List[str]:
    """
    Load negative ASINs from a text file.

    Supports comma-separated, newline-separated, or mixed format.

    Args:
        file_path: Path to the negatives file

    Returns:
        List of ASIN strings
    """
    path = Path(file_path)
    if not path.exists():
        return []

    content = path.read_text().strip()
    if not content:
        return []

    # Split by comma or newline, filter empty strings
    asins = []
    for item in content.replace('\n', ',').split(','):
        asin = item.strip()
        if asin and len(asin) == 10:  # Valid ASIN length
            asins.append(asin)

    return list(dict.fromkeys(asins))  # Deduplicate while preserving order


@dataclass
class GoalConfig:
    """Configuration for goal generation."""
    daily_budget: int = 10  # Legacy: total budget per SKU (now $100)
    target_acos: int = 30   # Legacy: default ACOS (now segment-specific)
    min_bid: float = 0.20
    max_bid: float = 2.00
    status: str = "Enabled"


# Budget allocation per campaign type (total $100 per SKU)
# Branded: 5% = $5 (split across 4 campaigns)
# Unbranded + Auto: 65% = $65 (split across 4 campaigns)
# Competitor: 30% = $30 (split across 4 campaigns)
BUDGET_ALLOCATION = {
    'BRANDED_EXACT': 1,
    'BRANDED_PHRASE': 1,
    'BRANDED_BROAD': 1,
    'BRANDED_PAT': 2,
    'MANUAL_EXACT': 16,
    'MANUAL_PHRASE': 16,
    'MANUAL_BROAD': 16,
    'AUTO': 17,
    'COMPETITOR_EXACT': 8,
    'COMPETITOR_PHRASE': 8,
    'COMPETITOR_BROAD': 7,
    'COMPETITOR_PAT': 7,
}

# ACOS allocation per segment
# Branded: 20%
# Unbranded/Competitor: 60%
ACOS_ALLOCATION = {
    'BRANDED_EXACT': 20,
    'BRANDED_PHRASE': 20,
    'BRANDED_BROAD': 20,
    'BRANDED_PAT': 20,
    'MANUAL_EXACT': 60,
    'MANUAL_PHRASE': 60,
    'MANUAL_BROAD': 60,
    'AUTO': 60,
    'COMPETITOR_EXACT': 60,
    'COMPETITOR_PHRASE': 60,
    'COMPETITOR_BROAD': 60,
    'COMPETITOR_PAT': 60,
}


# Perpetua CSV column mapping (0-indexed, but we use 1-indexed for clarity)
# Based on Perpetua documentation
COLUMNS = {
    'A': 'Record ID',
    'B': 'Record Type',           # SingleCampaign_KW or SingleCampaign_PAT or Product
    'C': 'Marketplace',
    'D': 'Goal Name',             # Max 60 chars
    'E': 'Goal ID',
    'F': 'Status',                # Enabled/Paused/Deleted
    'G': 'Start Date',
    'H': 'Daily Budget',          # Whole numbers >= 1
    'I': 'Target ACoS',           # Whole numbers >= 1
    'J': 'Smart Pilot Mode',
    'K': 'Smart Pilot Strategy',
    'L': 'Reserved',
    'M': 'Exact Keywords',        # Comma-separated (KW only)
    'N': 'Phrase Keywords',       # Comma-separated (KW only)
    'O': 'Broad Keywords',        # Comma-separated (KW only)
    'P': 'PAT Targets',           # Comma-separated (PAT only)
    'Q': 'Negative Exact',        # Comma-separated
    'R': 'Negative Phrase',       # Comma-separated
    'S': 'Reserved2',
    'T': 'Min Bid',               # Decimal >= 0
    'U': 'Max Bid',               # Decimal >= 0
    'V': 'Product ASIN',          # For Product rows
    'W': 'Product SKU',           # For Product rows
}


def generate_goal_name(sku: str, asin: str, campaign_type: str) -> str:
    """
    Generate goal name following naming convention.

    Format: SKU - JN - ASIN [SP_CAMPAIGN_TYPE]

    Args:
        sku: Product SKU
        asin: Product ASIN
        campaign_type: One of the 12 campaign type identifiers:
            - BRANDED_EXACT, BRANDED_PHRASE, BRANDED_BROAD, BRANDED_PAT
            - MANUAL_EXACT, MANUAL_PHRASE, MANUAL_BROAD
            - COMPETITOR_EXACT, COMPETITOR_PHRASE, COMPETITOR_BROAD, COMPETITOR_PAT
            - AUTO

    Returns:
        Formatted goal name (max 60 chars)
    """
    name = f"{sku} - JN - {asin} [SP_{campaign_type}]"
    return name[:60]  # Truncate to max 60 chars


# Campaign type definitions for 12-campaign structure (competitor split by match type)
CAMPAIGN_TYPES = [
    # (campaign_type_id, record_type, description)
    ('BRANDED_EXACT', 'SingleCampaign_KW', 'Branded - Exact'),
    ('BRANDED_PHRASE', 'SingleCampaign_KW', 'Branded - Phrase'),
    ('BRANDED_BROAD', 'SingleCampaign_KW', 'Branded - Broad'),
    ('BRANDED_PAT', 'SingleCampaign_PAT', 'Branded - PAT'),
    ('MANUAL_EXACT', 'SingleCampaign_KW', 'Unbranded - Exact'),
    ('MANUAL_PHRASE', 'SingleCampaign_KW', 'Unbranded - Phrase'),
    ('MANUAL_BROAD', 'SingleCampaign_KW', 'Unbranded - Broad'),
    ('COMPETITOR_EXACT', 'SingleCampaign_KW', 'Competitor - Exact'),
    ('COMPETITOR_PHRASE', 'SingleCampaign_KW', 'Competitor - Phrase'),
    ('COMPETITOR_BROAD', 'SingleCampaign_KW', 'Competitor - Broad'),
    ('COMPETITOR_PAT', 'SingleCampaign_PAT', 'Competitor - PAT'),
    ('AUTO', 'SingleCampaign_KW', 'Automatic'),
]


# Minimum budget failsafe
MIN_BUDGET = 5


def create_goal_row(
    goal_type: str,
    goal_name: str,
    config: GoalConfig,
    campaign_type: str,
    exact_kw: Optional[List[str]] = None,
    phrase_kw: Optional[List[str]] = None,
    broad_kw: Optional[List[str]] = None,
    pat_targets: Optional[List[str]] = None,
    negative_exact: Optional[List[str]] = None,
    negative_phrase: Optional[List[str]] = None,
    negative_asins: Optional[List[str]] = None,
) -> Dict:
    """Create a goal row for Perpetua CSV with segment-specific budget and ACOS."""
    row = {col: '' for col in COLUMNS.values()}

    # Get segment-specific budget and ACOS
    budget = BUDGET_ALLOCATION.get(campaign_type, config.daily_budget)
    acos = ACOS_ALLOCATION.get(campaign_type, config.target_acos)

    # Apply minimum budget failsafe
    if budget < MIN_BUDGET:
        budget = MIN_BUDGET

    row['Record Type'] = goal_type
    row['Goal Name'] = goal_name
    row['Status'] = config.status
    row['Daily Budget'] = budget
    row['Target ACoS'] = acos
    row['Min Bid'] = config.min_bid
    row['Max Bid'] = config.max_bid

    if exact_kw:
        row['Exact Keywords'] = ','.join(exact_kw)
    if phrase_kw:
        row['Phrase Keywords'] = ','.join(phrase_kw)
    if broad_kw:
        row['Broad Keywords'] = ','.join(broad_kw)
    if pat_targets:
        row['PAT Targets'] = ','.join(pat_targets)
    if negative_exact:
        row['Negative Exact'] = ','.join(negative_exact)
    if negative_phrase:
        row['Negative Phrase'] = ','.join(negative_phrase)
    # For PAT campaigns, negative ASINs go in the Negative Exact column
    if negative_asins:
        existing = row['Negative Exact']
        if existing:
            row['Negative Exact'] = existing + ',' + ','.join(negative_asins)
        else:
            row['Negative Exact'] = ','.join(negative_asins)

    return row


def create_product_row(asin: str, sku: str, status: str = "Enabled") -> Dict:
    """Create a product row for Perpetua CSV."""
    row = {col: '' for col in COLUMNS.values()}
    row['Record Type'] = 'Product'
    row['Status'] = status
    row['Product ASIN'] = asin
    row['Product SKU'] = sku
    return row


def generate_perpetua_csv(
    campaign_keywords: Dict[str, CampaignKeywords],
    config: GoalConfig,
    output_path: str,
    global_negative_asins: Optional[List[str]] = None
) -> str:
    """
    Generate Perpetua bulk upload CSV with 12 campaigns per SKU.

    Creates the following 12 campaign types per SKU:
    1. Branded - Exact: [SP_BRANDED_EXACT]
    2. Branded - Phrase: [SP_BRANDED_PHRASE]
    3. Branded - Broad: [SP_BRANDED_BROAD]
    4. Branded - PAT: [SP_BRANDED_PAT]
    5. Unbranded - Exact: [SP_MANUAL_EXACT]
    6. Unbranded - Phrase: [SP_MANUAL_PHRASE]
    7. Unbranded - Broad: [SP_MANUAL_BROAD]
    8. Competitor - Exact: [SP_COMPETITOR_EXACT]
    9. Competitor - Phrase: [SP_COMPETITOR_PHRASE]
    10. Competitor - Broad: [SP_COMPETITOR_BROAD]
    11. Competitor - PAT: [SP_COMPETITOR_PAT]
    12. Automatic: [SP_AUTO]

    Args:
        campaign_keywords: Dictionary mapping ASIN -> CampaignKeywords
        config: Goal configuration
        output_path: Path for output CSV
        global_negative_asins: List of ASINs to add as negatives to ALL PAT campaigns

    Returns:
        Path to generated CSV file
    """
    rows = []
    total_skus = len(campaign_keywords)
    progress = ProgressBar(total=total_skus, description="Generating goals")

    # Log global negatives if provided
    if global_negative_asins:
        print(f"  Applying {len(global_negative_asins)} global negative ASINs to PAT campaigns")

    for asin, kw_data in campaign_keywords.items():
        sku = kw_data.sku

        # 1. Branded - Exact
        if kw_data.branded_exact:
            negs = kw_data.get_negatives('branded_exact')
            goal_name = generate_goal_name(sku, asin, 'BRANDED_EXACT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='BRANDED_EXACT',
                exact_kw=kw_data.branded_exact,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 2. Branded - Phrase
        if kw_data.branded_phrase:
            negs = kw_data.get_negatives('branded_phrase')
            goal_name = generate_goal_name(sku, asin, 'BRANDED_PHRASE')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='BRANDED_PHRASE',
                phrase_kw=kw_data.branded_phrase,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 3. Branded - Broad
        if kw_data.branded_broad:
            negs = kw_data.get_negatives('branded_broad')
            goal_name = generate_goal_name(sku, asin, 'BRANDED_BROAD')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='BRANDED_BROAD',
                broad_kw=kw_data.branded_broad,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 4. Branded - PAT (uses negative ASINs stored in campaign_negatives + global negatives)
        if kw_data.branded_pat_targets:
            negs = kw_data.get_negatives('branded_pat')
            goal_name = generate_goal_name(sku, asin, 'BRANDED_PAT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_PAT',
                goal_name=goal_name,
                config=config,
                campaign_type='BRANDED_PAT',
                pat_targets=kw_data.branded_pat_targets,
                negative_asins=global_negative_asins
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 5. Unbranded - Exact
        if kw_data.unbranded_exact:
            negs = kw_data.get_negatives('unbranded_exact')
            goal_name = generate_goal_name(sku, asin, 'MANUAL_EXACT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='MANUAL_EXACT',
                exact_kw=kw_data.unbranded_exact,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 6. Unbranded - Phrase
        if kw_data.unbranded_phrase:
            negs = kw_data.get_negatives('unbranded_phrase')
            goal_name = generate_goal_name(sku, asin, 'MANUAL_PHRASE')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='MANUAL_PHRASE',
                phrase_kw=kw_data.unbranded_phrase,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 7. Unbranded - Broad
        if kw_data.unbranded_broad:
            negs = kw_data.get_negatives('unbranded_broad')
            goal_name = generate_goal_name(sku, asin, 'MANUAL_BROAD')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='MANUAL_BROAD',
                broad_kw=kw_data.unbranded_broad,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 8. Competitor - Exact
        if kw_data.competitor_exact:
            negs = kw_data.get_negatives('competitor_exact')
            goal_name = generate_goal_name(sku, asin, 'COMPETITOR_EXACT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='COMPETITOR_EXACT',
                exact_kw=kw_data.competitor_exact,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 9. Competitor - Phrase
        if kw_data.competitor_phrase:
            negs = kw_data.get_negatives('competitor_phrase')
            goal_name = generate_goal_name(sku, asin, 'COMPETITOR_PHRASE')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='COMPETITOR_PHRASE',
                phrase_kw=kw_data.competitor_phrase,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 10. Competitor - Broad
        if kw_data.competitor_broad:
            negs = kw_data.get_negatives('competitor_broad')
            goal_name = generate_goal_name(sku, asin, 'COMPETITOR_BROAD')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='COMPETITOR_BROAD',
                broad_kw=kw_data.competitor_broad,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 11. Competitor - PAT (uses negative ASINs stored in campaign_negatives + global negatives)
        if kw_data.competitor_pat_targets:
            negs = kw_data.get_negatives('competitor_pat')
            goal_name = generate_goal_name(sku, asin, 'COMPETITOR_PAT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_PAT',
                goal_name=goal_name,
                config=config,
                campaign_type='COMPETITOR_PAT',
                pat_targets=kw_data.competitor_pat_targets,
                negative_asins=global_negative_asins
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 12. Automatic
        if kw_data.auto_keywords:
            negs = kw_data.get_negatives('auto')
            goal_name = generate_goal_name(sku, asin, 'AUTO')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                campaign_type='AUTO',
                exact_kw=kw_data.auto_keywords,
                negative_exact=negs['exact'] if negs['exact'] else None,
                negative_phrase=negs['phrase'] if negs['phrase'] else None
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        progress.update(1)

    progress.close()

    # Create DataFrame and save
    with Spinner("Saving CSV file...", style="dots"):
        df = pd.DataFrame(rows)

        # Reorder columns to match Perpetua expected format
        column_order = list(COLUMNS.values())
        df = df.reindex(columns=column_order)

        df.to_csv(output_path, index=False)

    print(f"✓ Saved {len(rows):,} rows to {output_path}")
    return output_path


def generate_empty_goals_for_asins(
    asin_sku_map: Dict[str, str],
    config: GoalConfig,
    output_path: str
) -> str:
    """
    Generate Perpetua CSV with empty goals (no keywords) for manual filling.

    Creates empty templates for all 12 campaign types per SKU:
    1. Branded - Exact: [SP_BRANDED_EXACT]
    2. Branded - Phrase: [SP_BRANDED_PHRASE]
    3. Branded - Broad: [SP_BRANDED_BROAD]
    4. Branded - PAT: [SP_BRANDED_PAT]
    5. Unbranded - Exact: [SP_MANUAL_EXACT]
    6. Unbranded - Phrase: [SP_MANUAL_PHRASE]
    7. Unbranded - Broad: [SP_MANUAL_BROAD]
    8. Competitor - Exact: [SP_COMPETITOR_EXACT]
    9. Competitor - Phrase: [SP_COMPETITOR_PHRASE]
    10. Competitor - Broad: [SP_COMPETITOR_BROAD]
    11. Competitor - PAT: [SP_COMPETITOR_PAT]
    12. Automatic: [SP_AUTO]

    Args:
        asin_sku_map: Dictionary mapping ASIN -> SKU
        config: Goal configuration
        output_path: Path for output CSV

    Returns:
        Path to generated CSV file
    """
    rows = []
    total_skus = len(asin_sku_map)
    progress = ProgressBar(total=total_skus, description="Generating goals")

    for asin, sku in asin_sku_map.items():
        # Create all 12 campaign types using CAMPAIGN_TYPES constant
        for campaign_type_id, record_type, _ in CAMPAIGN_TYPES:
            goal_name = generate_goal_name(sku, asin, campaign_type_id)
            goal_row = create_goal_row(
                goal_type=record_type,
                goal_name=goal_name,
                config=config,
                campaign_type=campaign_type_id
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        progress.update(1)

    progress.close()

    with Spinner("Saving CSV file...", style="dots"):
        df = pd.DataFrame(rows)
        column_order = list(COLUMNS.values())
        df = df.reindex(columns=column_order)
        df.to_csv(output_path, index=False)

    print(f"✓ Saved {len(rows):,} rows to {output_path}")
    return output_path


if __name__ == '__main__':
    from keyword_extractor import load_asin_sku_map

    # Example usage
    asin_sku_map = load_asin_sku_map('ASIN and SKU.csv')

    config = GoalConfig(
        daily_budget=10,
        target_acos=30,
        min_bid=0.20,
        max_bid=2.00
    )

    # Generate empty template
    output = generate_empty_goals_for_asins(
        asin_sku_map=asin_sku_map,
        config=config,
        output_path='perpetua_goals_template.csv'
    )
    print(f"Generated template: {output}")
