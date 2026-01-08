#!/usr/bin/env python3
"""
Perpetua Goal Generator - Main Script

Generate Perpetua bulk upload CSV files for Custom (Single-Campaign) Goals.
Supports extracting keywords from existing Amazon campaigns.

Usage:
    python main.py --help
    python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv
    python main.py generate --asin-sku "ASIN and SKU.csv" --amazon-export bulk.xlsx --output goals.csv
"""

import argparse
import sys
from pathlib import Path

from keyword_extractor import (
    load_asin_sku_map,
    extract_keywords_from_amazon_bulk,
    CampaignKeywords
)
from perpetua_generator import (
    GoalConfig,
    generate_perpetua_csv,
    generate_empty_goals_for_asins
)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate Perpetua bulk upload CSV for Custom Goals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate empty template:
    python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv

  Generate with keywords from Amazon export:
    python main.py generate --asin-sku "ASIN and SKU.csv" --amazon-export bulk.xlsx --output goals.csv

  Custom configuration:
    python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv \\
        --budget 15 --acos 25 --min-bid 0.30 --max-bid 3.00

Naming Convention:
  SKU - ASIN [SP_SEGMENT_MATCHTYPE] JN
  Example: NT15511A - B07Y5L9WLP [SP_KEYWORD_EXACT] JN
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate Perpetua CSV')
    gen_parser.add_argument(
        '--asin-sku', '-a',
        required=True,
        help='Path to ASIN/SKU CSV file'
    )
    gen_parser.add_argument(
        '--amazon-export', '-e',
        help='Path to Amazon Ads bulk export file (optional)'
    )
    gen_parser.add_argument(
        '--output', '-o',
        default='perpetua_goals.csv',
        help='Output CSV file path (default: perpetua_goals.csv)'
    )
    gen_parser.add_argument(
        '--budget',
        type=int,
        default=10,
        help='Daily budget (default: 10)'
    )
    gen_parser.add_argument(
        '--acos',
        type=int,
        default=30,
        help='Target ACoS (default: 30)'
    )
    gen_parser.add_argument(
        '--min-bid',
        type=float,
        default=0.20,
        help='Minimum bid (default: 0.20)'
    )
    gen_parser.add_argument(
        '--max-bid',
        type=float,
        default=2.00,
        help='Maximum bid (default: 2.00)'
    )
    gen_parser.add_argument(
        '--status',
        choices=['Enabled', 'Paused'],
        default='Enabled',
        help='Goal status (default: Enabled)'
    )
    gen_parser.add_argument(
        '--kw-only',
        action='store_true',
        help='Generate only keyword targeting goals'
    )
    gen_parser.add_argument(
        '--pat-only',
        action='store_true',
        help='Generate only PAT goals'
    )
    gen_parser.add_argument(
        '--combined',
        action='store_true',
        help='Combine all match types into single goal (default: separate goals)'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if not args.command:
        print("Usage: python main.py generate --asin-sku <file> --output <file>")
        print("Run 'python main.py --help' for more options.")
        sys.exit(1)

    if args.command == 'generate':
        # Validate input file
        asin_sku_path = Path(args.asin_sku)
        if not asin_sku_path.exists():
            print(f"Error: ASIN/SKU file not found: {args.asin_sku}")
            sys.exit(1)

        # Load ASIN/SKU mapping
        print(f"Loading ASIN/SKU data from: {args.asin_sku}")
        asin_sku_map = load_asin_sku_map(args.asin_sku)
        print(f"  Found {len(asin_sku_map)} products")

        # Create configuration
        config = GoalConfig(
            daily_budget=args.budget,
            target_acos=args.acos,
            min_bid=args.min_bid,
            max_bid=args.max_bid,
            status=args.status
        )

        # Determine goal types
        generate_kw = not args.pat_only
        generate_pat = not args.kw_only

        if args.amazon_export:
            # Extract keywords from Amazon export
            export_path = Path(args.amazon_export)
            if not export_path.exists():
                print(f"Error: Amazon export file not found: {args.amazon_export}")
                sys.exit(1)

            print(f"Extracting keywords from: {args.amazon_export}")
            campaign_keywords = extract_keywords_from_amazon_bulk(
                args.amazon_export,
                asin_sku_map
            )

            # Count keywords
            total_exact = sum(len(kw.exact_keywords) for kw in campaign_keywords.values())
            total_phrase = sum(len(kw.phrase_keywords) for kw in campaign_keywords.values())
            total_broad = sum(len(kw.broad_keywords) for kw in campaign_keywords.values())
            total_pat = sum(len(kw.pat_targets) for kw in campaign_keywords.values())

            print(f"  Extracted keywords:")
            print(f"    Exact: {total_exact}")
            print(f"    Phrase: {total_phrase}")
            print(f"    Broad: {total_broad}")
            print(f"    PAT targets: {total_pat}")

            # Generate CSV with keywords
            output = generate_perpetua_csv(
                campaign_keywords=campaign_keywords,
                config=config,
                output_path=args.output,
                generate_kw=generate_kw,
                generate_pat=generate_pat,
                split_by_match_type=not args.combined
            )
        else:
            # Generate empty template
            print("No Amazon export provided - generating empty template")
            output = generate_empty_goals_for_asins(
                asin_sku_map=asin_sku_map,
                config=config,
                output_path=args.output,
                generate_kw=generate_kw,
                generate_pat=generate_pat
            )

        print(f"\nGenerated: {output}")
        print(f"\nGoal naming convention: SKU - ASIN [SP_SEGMENT_MATCHTYPE] JN")
        print(f"Configuration:")
        print(f"  Daily Budget: ${config.daily_budget}")
        print(f"  Target ACoS: {config.target_acos}%")
        print(f"  Bid Range: ${config.min_bid:.2f} - ${config.max_bid:.2f}")
        print(f"  Status: {config.status}")


if __name__ == '__main__':
    main()
