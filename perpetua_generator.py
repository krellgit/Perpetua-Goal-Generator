"""
Perpetua Goal Generator

Generates CSV files for Perpetua bulk operations to launch/edit
Custom (Single-Campaign) Goals with proper naming convention.

Naming Convention: SKU - ASIN [SP_SEGMENT_MATCHTYPE] JN
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from keyword_extractor import CampaignKeywords


@dataclass
class GoalConfig:
    """Configuration for goal generation."""
    daily_budget: int = 10
    target_acos: int = 30
    min_bid: float = 0.20
    max_bid: float = 2.00
    status: str = "Enabled"


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

    Format: SKU - ASIN [SP_CAMPAIGN_TYPE] JN

    Args:
        sku: Product SKU
        asin: Product ASIN
        campaign_type: One of the 10 campaign type identifiers:
            - BRANDED_EXACT, BRANDED_PHRASE, BRANDED_BROAD, BRANDED_PAT
            - MANUAL_EXACT, MANUAL_PHRASE, MANUAL_BROAD
            - COMPETITOR_KW, COMPETITOR_PAT
            - AUTO

    Returns:
        Formatted goal name (max 60 chars)
    """
    name = f"{sku} - {asin} [SP_{campaign_type}] JN"
    return name[:60]  # Truncate to max 60 chars


# Campaign type definitions for 10-campaign structure
CAMPAIGN_TYPES = [
    # (campaign_type_id, record_type, description)
    ('BRANDED_EXACT', 'SingleCampaign_KW', 'Branded - Exact'),
    ('BRANDED_PHRASE', 'SingleCampaign_KW', 'Branded - Phrase'),
    ('BRANDED_BROAD', 'SingleCampaign_KW', 'Branded - Broad'),
    ('BRANDED_PAT', 'SingleCampaign_PAT', 'Branded - PAT'),
    ('MANUAL_EXACT', 'SingleCampaign_KW', 'Unbranded - Exact'),
    ('MANUAL_PHRASE', 'SingleCampaign_KW', 'Unbranded - Phrase'),
    ('MANUAL_BROAD', 'SingleCampaign_KW', 'Unbranded - Broad'),
    ('COMPETITOR_KW', 'SingleCampaign_KW', 'Competitor - KW'),
    ('COMPETITOR_PAT', 'SingleCampaign_PAT', 'Competitor - PAT'),
    ('AUTO', 'SingleCampaign_KW', 'Automatic'),
]


def create_goal_row(
    goal_type: str,
    goal_name: str,
    config: GoalConfig,
    exact_kw: Optional[List[str]] = None,
    phrase_kw: Optional[List[str]] = None,
    broad_kw: Optional[List[str]] = None,
    pat_targets: Optional[List[str]] = None,
    negative_exact: Optional[List[str]] = None,
    negative_phrase: Optional[List[str]] = None,
) -> Dict:
    """Create a goal row for Perpetua CSV."""
    row = {col: '' for col in COLUMNS.values()}

    row['Record Type'] = goal_type
    row['Goal Name'] = goal_name
    row['Status'] = config.status
    row['Daily Budget'] = config.daily_budget
    row['Target ACoS'] = config.target_acos
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
    output_path: str
) -> str:
    """
    Generate Perpetua bulk upload CSV with 10 campaigns per SKU.

    Creates the following 10 campaign types per SKU:
    1. Branded - Exact: [SP_BRANDED_EXACT]
    2. Branded - Phrase: [SP_BRANDED_PHRASE]
    3. Branded - Broad: [SP_BRANDED_BROAD]
    4. Branded - PAT: [SP_BRANDED_PAT]
    5. Unbranded - Exact: [SP_MANUAL_EXACT]
    6. Unbranded - Phrase: [SP_MANUAL_PHRASE]
    7. Unbranded - Broad: [SP_MANUAL_BROAD]
    8. Competitor - KW: [SP_COMPETITOR_KW]
    9. Competitor - PAT: [SP_COMPETITOR_PAT]
    10. Automatic: [SP_AUTO]

    Args:
        campaign_keywords: Dictionary mapping ASIN -> CampaignKeywords
        config: Goal configuration
        output_path: Path for output CSV

    Returns:
        Path to generated CSV file
    """
    rows = []

    for asin, kw_data in campaign_keywords.items():
        sku = kw_data.sku

        # 1. Branded - Exact
        if kw_data.branded_exact:
            goal_name = generate_goal_name(sku, asin, 'BRANDED_EXACT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                exact_kw=kw_data.branded_exact,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 2. Branded - Phrase
        if kw_data.branded_phrase:
            goal_name = generate_goal_name(sku, asin, 'BRANDED_PHRASE')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                phrase_kw=kw_data.branded_phrase,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 3. Branded - Broad
        if kw_data.branded_broad:
            goal_name = generate_goal_name(sku, asin, 'BRANDED_BROAD')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                broad_kw=kw_data.branded_broad,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 4. Branded - PAT
        if kw_data.branded_pat_targets:
            goal_name = generate_goal_name(sku, asin, 'BRANDED_PAT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_PAT',
                goal_name=goal_name,
                config=config,
                pat_targets=kw_data.branded_pat_targets,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 5. Unbranded - Exact
        if kw_data.unbranded_exact:
            goal_name = generate_goal_name(sku, asin, 'MANUAL_EXACT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                exact_kw=kw_data.unbranded_exact,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 6. Unbranded - Phrase
        if kw_data.unbranded_phrase:
            goal_name = generate_goal_name(sku, asin, 'MANUAL_PHRASE')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                phrase_kw=kw_data.unbranded_phrase,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 7. Unbranded - Broad
        if kw_data.unbranded_broad:
            goal_name = generate_goal_name(sku, asin, 'MANUAL_BROAD')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                broad_kw=kw_data.unbranded_broad,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 8. Competitor - KW (all match types combined as exact)
        if kw_data.competitor_keywords:
            goal_name = generate_goal_name(sku, asin, 'COMPETITOR_KW')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                exact_kw=kw_data.competitor_keywords,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 9. Competitor - PAT
        if kw_data.competitor_pat_targets:
            goal_name = generate_goal_name(sku, asin, 'COMPETITOR_PAT')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_PAT',
                goal_name=goal_name,
                config=config,
                pat_targets=kw_data.competitor_pat_targets,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

        # 10. Automatic
        if kw_data.auto_keywords:
            goal_name = generate_goal_name(sku, asin, 'AUTO')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_KW',
                goal_name=goal_name,
                config=config,
                exact_kw=kw_data.auto_keywords,
                negative_exact=kw_data.negative_exact,
                negative_phrase=kw_data.negative_phrase
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

    # Create DataFrame and save
    df = pd.DataFrame(rows)

    # Reorder columns to match Perpetua expected format
    column_order = list(COLUMNS.values())
    df = df.reindex(columns=column_order)

    df.to_csv(output_path, index=False)
    return output_path


def generate_empty_goals_for_asins(
    asin_sku_map: Dict[str, str],
    config: GoalConfig,
    output_path: str
) -> str:
    """
    Generate Perpetua CSV with empty goals (no keywords) for manual filling.

    Creates empty templates for all 10 campaign types per SKU:
    1. Branded - Exact: [SP_BRANDED_EXACT]
    2. Branded - Phrase: [SP_BRANDED_PHRASE]
    3. Branded - Broad: [SP_BRANDED_BROAD]
    4. Branded - PAT: [SP_BRANDED_PAT]
    5. Unbranded - Exact: [SP_MANUAL_EXACT]
    6. Unbranded - Phrase: [SP_MANUAL_PHRASE]
    7. Unbranded - Broad: [SP_MANUAL_BROAD]
    8. Competitor - KW: [SP_COMPETITOR_KW]
    9. Competitor - PAT: [SP_COMPETITOR_PAT]
    10. Automatic: [SP_AUTO]

    Args:
        asin_sku_map: Dictionary mapping ASIN -> SKU
        config: Goal configuration
        output_path: Path for output CSV

    Returns:
        Path to generated CSV file
    """
    rows = []

    for asin, sku in asin_sku_map.items():
        # Create all 10 campaign types using CAMPAIGN_TYPES constant
        for campaign_type_id, record_type, _ in CAMPAIGN_TYPES:
            goal_name = generate_goal_name(sku, asin, campaign_type_id)
            goal_row = create_goal_row(
                goal_type=record_type,
                goal_name=goal_name,
                config=config
            )
            rows.append(goal_row)
            rows.append(create_product_row(asin, sku))

    df = pd.DataFrame(rows)
    column_order = list(COLUMNS.values())
    df = df.reindex(columns=column_order)
    df.to_csv(output_path, index=False)
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
