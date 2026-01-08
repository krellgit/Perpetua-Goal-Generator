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


def generate_goal_name(sku: str, asin: str, segment: str, match_type: str) -> str:
    """
    Generate goal name following naming convention.

    Format: SKU - ASIN [SP_SEGMENT_MATCHTYPE] JN

    Args:
        sku: Product SKU
        asin: Product ASIN
        segment: KEYWORD or PAT
        match_type: EXACT, PHRASE, BROAD, or ASIN

    Returns:
        Formatted goal name (max 60 chars)
    """
    name = f"{sku} - {asin} [SP_{segment}_{match_type}] JN"
    return name[:60]  # Truncate to max 60 chars


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
    output_path: str,
    generate_kw: bool = True,
    generate_pat: bool = True,
    split_by_match_type: bool = True
) -> str:
    """
    Generate Perpetua bulk upload CSV.

    Args:
        campaign_keywords: Dictionary mapping ASIN -> CampaignKeywords
        config: Goal configuration
        output_path: Path for output CSV
        generate_kw: Generate keyword targeting goals
        generate_pat: Generate PAT goals
        split_by_match_type: If True, create separate goals for each match type

    Returns:
        Path to generated CSV file
    """
    rows = []

    for asin, kw_data in campaign_keywords.items():
        sku = kw_data.sku

        if generate_kw:
            if split_by_match_type:
                # Create separate goals for each match type
                if kw_data.exact_keywords:
                    goal_name = generate_goal_name(sku, asin, 'KEYWORD', 'EXACT')
                    goal_row = create_goal_row(
                        goal_type='SingleCampaign_KW',
                        goal_name=goal_name,
                        config=config,
                        exact_kw=kw_data.exact_keywords,
                        negative_exact=kw_data.negative_exact,
                        negative_phrase=kw_data.negative_phrase
                    )
                    rows.append(goal_row)
                    rows.append(create_product_row(asin, sku))

                if kw_data.phrase_keywords:
                    goal_name = generate_goal_name(sku, asin, 'KEYWORD', 'PHRASE')
                    goal_row = create_goal_row(
                        goal_type='SingleCampaign_KW',
                        goal_name=goal_name,
                        config=config,
                        phrase_kw=kw_data.phrase_keywords,
                        negative_exact=kw_data.negative_exact,
                        negative_phrase=kw_data.negative_phrase
                    )
                    rows.append(goal_row)
                    rows.append(create_product_row(asin, sku))

                if kw_data.broad_keywords:
                    goal_name = generate_goal_name(sku, asin, 'KEYWORD', 'BROAD')
                    goal_row = create_goal_row(
                        goal_type='SingleCampaign_KW',
                        goal_name=goal_name,
                        config=config,
                        broad_kw=kw_data.broad_keywords,
                        negative_exact=kw_data.negative_exact,
                        negative_phrase=kw_data.negative_phrase
                    )
                    rows.append(goal_row)
                    rows.append(create_product_row(asin, sku))
            else:
                # Combined keyword goal
                has_keywords = (kw_data.exact_keywords or
                               kw_data.phrase_keywords or
                               kw_data.broad_keywords)
                if has_keywords:
                    goal_name = generate_goal_name(sku, asin, 'KEYWORD', 'ALL')
                    goal_row = create_goal_row(
                        goal_type='SingleCampaign_KW',
                        goal_name=goal_name,
                        config=config,
                        exact_kw=kw_data.exact_keywords,
                        phrase_kw=kw_data.phrase_keywords,
                        broad_kw=kw_data.broad_keywords,
                        negative_exact=kw_data.negative_exact,
                        negative_phrase=kw_data.negative_phrase
                    )
                    rows.append(goal_row)
                    rows.append(create_product_row(asin, sku))

        if generate_pat and kw_data.pat_targets:
            goal_name = generate_goal_name(sku, asin, 'PAT', 'ASIN')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_PAT',
                goal_name=goal_name,
                config=config,
                pat_targets=kw_data.pat_targets,
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
    output_path: str,
    generate_kw: bool = True,
    generate_pat: bool = True
) -> str:
    """
    Generate Perpetua CSV with empty goals (no keywords) for manual filling.

    Args:
        asin_sku_map: Dictionary mapping ASIN -> SKU
        config: Goal configuration
        output_path: Path for output CSV
        generate_kw: Generate keyword targeting goals
        generate_pat: Generate PAT goals

    Returns:
        Path to generated CSV file
    """
    rows = []

    for asin, sku in asin_sku_map.items():
        if generate_kw:
            # Create placeholder KW goals for each match type
            for match_type in ['EXACT', 'PHRASE', 'BROAD']:
                goal_name = generate_goal_name(sku, asin, 'KEYWORD', match_type)
                goal_row = create_goal_row(
                    goal_type='SingleCampaign_KW',
                    goal_name=goal_name,
                    config=config
                )
                rows.append(goal_row)
                rows.append(create_product_row(asin, sku))

        if generate_pat:
            goal_name = generate_goal_name(sku, asin, 'PAT', 'ASIN')
            goal_row = create_goal_row(
                goal_type='SingleCampaign_PAT',
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
