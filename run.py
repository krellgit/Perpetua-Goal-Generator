#!/usr/bin/env python3
"""
Simple runner for Perpetua Goal Generator.

Default file names:
  - ASINList.csv  (your ASIN/SKU list)
  - bulk.xlsx     (Amazon bulk export)
  - trimmed.xlsx  (trimmed output)
  - goals.csv     (Perpetua output)

Usage:
  python run.py trim       # Trim bulk.xlsx -> trimmed.xlsx
  python run.py generate   # Generate goals.csv from trimmed.xlsx
  python run.py all        # Do both: trim then generate
  python run.py template   # Generate empty template (no keywords)
"""

import sys
import subprocess
from pathlib import Path

# Default file names
ASIN_FILE = "ASINList.csv"
BULK_FILE = "bulk.xlsx"
TRIMMED_FILE = "trimmed.xlsx"
OUTPUT_FILE = "goals.csv"


def run_command(cmd):
    """Run a command and print output."""
    print(f"\n> {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nFiles in directory:")
        for f in Path(".").glob("*.csv"):
            print(f"  {f}")
        for f in Path(".").glob("*.xlsx"):
            print(f"  {f}")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "trim":
        # Check bulk file exists
        if not Path(BULK_FILE).exists():
            print(f"Error: {BULK_FILE} not found!")
            print("Place your Amazon bulk export as 'bulk.xlsx' in this folder.")
            sys.exit(1)

        run_command([
            "python3", "main.py", "trim",
            "--bulk-file", BULK_FILE,
            "--asin-sku", ASIN_FILE,
            "--output", TRIMMED_FILE
        ])

    elif command == "generate":
        # Use trimmed file if it exists, otherwise check for bulk
        export_file = TRIMMED_FILE if Path(TRIMMED_FILE).exists() else BULK_FILE

        if Path(export_file).exists():
            run_command([
                "python3", "main.py", "generate",
                "--asin-sku", ASIN_FILE,
                "--amazon-export", export_file,
                "--output", OUTPUT_FILE
            ])
        else:
            print(f"No export file found ({TRIMMED_FILE} or {BULK_FILE})")
            print("Generating empty template instead...")
            run_command([
                "python3", "main.py", "generate",
                "--asin-sku", ASIN_FILE,
                "--output", OUTPUT_FILE
            ])

    elif command == "all":
        # Trim then generate
        if Path(BULK_FILE).exists():
            print("=== Step 1: Trimming bulk file ===")
            if run_command([
                "python3", "main.py", "trim",
                "--bulk-file", BULK_FILE,
                "--asin-sku", ASIN_FILE,
                "--output", TRIMMED_FILE
            ]):
                print("\n=== Step 2: Generating goals ===")
                run_command([
                    "python3", "main.py", "generate",
                    "--asin-sku", ASIN_FILE,
                    "--amazon-export", TRIMMED_FILE,
                    "--output", OUTPUT_FILE
                ])
        else:
            print(f"Error: {BULK_FILE} not found!")
            sys.exit(1)

    elif command == "template":
        # Generate empty template
        run_command([
            "python3", "main.py", "generate",
            "--asin-sku", ASIN_FILE,
            "--output", OUTPUT_FILE
        ])

    else:
        print(f"Unknown command: {command}")
        print("Use: trim, generate, all, or template")
        sys.exit(1)


if __name__ == "__main__":
    main()
