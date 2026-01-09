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
    generate_empty_goals_for_asins,
    load_negative_asins
)
from bulk_trimmer import (
    load_asin_list_from_csv,
    trim_bulk_file
)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate Perpetua bulk upload CSV for Custom Goals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Trim a large bulk export to only your ASINs:
    python main.py trim --bulk-file export.xlsx --asin-sku "ASIN and SKU.csv" --output trimmed.xlsx

  Generate empty template (10 campaigns per SKU):
    python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv

  Generate with keywords from Amazon export:
    python main.py generate --asin-sku "ASIN and SKU.csv" --amazon-export bulk.xlsx --output goals.csv

  Custom configuration:
    python main.py generate --asin-sku "ASIN and SKU.csv" --output goals.csv \\
        --budget 15 --acos 25 --min-bid 0.30 --max-bid 3.00

12-Campaign Structure per SKU:
  1. [SP_BRANDED_EXACT] JN      - Branded exact keywords
  2. [SP_BRANDED_PHRASE] JN     - Branded phrase keywords
  3. [SP_BRANDED_BROAD] JN      - Branded broad keywords
  4. [SP_BRANDED_PAT] JN        - Branded PAT targets
  5. [SP_MANUAL_EXACT] JN       - Unbranded exact keywords
  6. [SP_MANUAL_PHRASE] JN      - Unbranded phrase keywords
  7. [SP_MANUAL_BROAD] JN       - Unbranded broad keywords
  8. [SP_COMPETITOR_EXACT] JN   - Competitor exact keywords
  9. [SP_COMPETITOR_PHRASE] JN  - Competitor phrase keywords
  10. [SP_COMPETITOR_BROAD] JN  - Competitor broad keywords
  11. [SP_COMPETITOR_PAT] JN    - Competitor PAT targets
  12. [SP_AUTO] JN              - Automatic campaign keywords
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Trim command
    trim_parser = subparsers.add_parser('trim', help='Trim large bulk export files by ASIN list')
    trim_parser.add_argument(
        '--bulk-file', '-b',
        required=True,
        help='Path to the bulk export file (.csv or .xlsx)'
    )
    trim_parser.add_argument(
        '--asin-sku', '-a',
        required=True,
        help='Path to ASIN/SKU CSV file (ASINs to keep)'
    )
    trim_parser.add_argument(
        '--output', '-o',
        required=True,
        help='Path for the trimmed output file'
    )
    trim_parser.add_argument(
        '--chunk-size',
        type=int,
        default=50000,
        help='Rows to process at a time (default: 50000)'
    )

    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate Perpetua CSV (10 campaigns per SKU)')
    gen_parser.add_argument(
        '--asin-sku', '-a',
        required=True,
        help='Path to ASIN/SKU CSV file'
    )
    gen_parser.add_argument(
        '--amazon-export', '-e',
        help='Path to Amazon Ads bulk export file (optional, use trimmed file for best results)'
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
        '--negatives', '-n',
        help='Path to negative ASINs file for PAT campaigns (optional)'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if not args.command:
        print("Usage: python main.py <command> [options]")
        print("Commands: trim, generate")
        print("Run 'python main.py --help' for more options.")
        sys.exit(1)

    if args.command == 'trim':
        # Validate input files
        bulk_path = Path(args.bulk_file)
        if not bulk_path.exists():
            print(f"Error: Bulk file not found: {args.bulk_file}")
            sys.exit(1)

        asin_sku_path = Path(args.asin_sku)
        if not asin_sku_path.exists():
            print(f"Error: ASIN/SKU file not found: {args.asin_sku}")
            sys.exit(1)

        # Load ASIN list
        print(f"Loading ASIN list from: {args.asin_sku}")
        asin_list = load_asin_list_from_csv(args.asin_sku)
        print(f"  Found {len(asin_list)} unique ASINs")
        print()

        # Trim bulk file
        try:
            trim_bulk_file(
                args.bulk_file,
                asin_list,
                args.output,
                chunk_size=args.chunk_size
            )
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == 'generate':
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

            # Count keywords by segment
            total_branded = sum(
                len(kw.branded_exact) + len(kw.branded_phrase) + len(kw.branded_broad)
                for kw in campaign_keywords.values()
            )
            total_unbranded = sum(
                len(kw.unbranded_exact) + len(kw.unbranded_phrase) + len(kw.unbranded_broad)
                for kw in campaign_keywords.values()
            )
            total_competitor = sum(
                len(kw.competitor_exact) + len(kw.competitor_phrase) + len(kw.competitor_broad)
                for kw in campaign_keywords.values()
            )
            total_branded_pat = sum(len(kw.branded_pat_targets) for kw in campaign_keywords.values())
            total_competitor_pat = sum(len(kw.competitor_pat_targets) for kw in campaign_keywords.values())
            total_auto = sum(len(kw.auto_keywords) for kw in campaign_keywords.values())

            print(f"  Extracted keywords by segment:")
            print(f"    Branded (KW): {total_branded}")
            print(f"    Unbranded (KW): {total_unbranded}")
            print(f"    Competitor (KW): {total_competitor}")
            print(f"    Branded (PAT): {total_branded_pat}")
            print(f"    Competitor (PAT): {total_competitor_pat}")
            print(f"    Auto: {total_auto}")

            # Load global negative ASINs for PAT campaigns if provided
            global_negative_asins = None
            if args.negatives:
                global_negative_asins = load_negative_asins(args.negatives)
                if global_negative_asins:
                    print(f"  Loaded {len(global_negative_asins)} negative ASINs for PAT campaigns")

            # Generate CSV with keywords
            output = generate_perpetua_csv(
                campaign_keywords=campaign_keywords,
                config=config,
                output_path=args.output,
                global_negative_asins=global_negative_asins
            )
        else:
            # Generate empty template
            print("No Amazon export provided - generating empty template (10 campaigns per SKU)")
            output = generate_empty_goals_for_asins(
                asin_sku_map=asin_sku_map,
                config=config,
                output_path=args.output
            )

        print(f"\nGenerated: {output}")
        print(f"\n12-Campaign Structure per SKU:")
        print(f"  [SP_BRANDED_EXACT], [SP_BRANDED_PHRASE], [SP_BRANDED_BROAD], [SP_BRANDED_PAT]")
        print(f"  [SP_MANUAL_EXACT], [SP_MANUAL_PHRASE], [SP_MANUAL_BROAD]")
        print(f"  [SP_COMPETITOR_EXACT], [SP_COMPETITOR_PHRASE], [SP_COMPETITOR_BROAD], [SP_COMPETITOR_PAT]")
        print(f"  [SP_AUTO]")
        print(f"\nConfiguration:")
        print(f"  Daily Budget: ${config.daily_budget}")
        print(f"  Target ACoS: {config.target_acos}%")
        print(f"  Bid Range: ${config.min_bid:.2f} - ${config.max_bid:.2f}")
        print(f"  Status: {config.status}")


if __name__ == '__main__':
    main()
