"""
Bulk Trimmer - Filter large Amazon Ads bulk export files by ASIN list.

Efficiently processes 600-700MB Excel/CSV files by filtering rows to only
include ASINs from a provided ASIN list.
"""

import os
import sys
import csv
from pathlib import Path
from typing import List, Optional, Dict, Any

import pandas as pd

from progress import ProgressBar, Spinner


# Common ASIN column name variations in Amazon Ads bulk exports
ASIN_COLUMN_VARIATIONS = [
    'ASIN',
    'ASIN (Informational only)',
    'Advertised ASIN',
    'Product ASIN',
    'asin',
    'advertised_asin',
    'product_asin',
    'Asin',
]


def load_asin_list_from_csv(csv_path: str) -> List[str]:
    """
    Load a list of ASINs from a CSV file.

    Args:
        csv_path: Path to CSV file containing ASINs.
                  Can have a header row with 'ASIN' or similar, or just ASINs.

    Returns:
        List of ASIN strings (deduplicated).
    """
    asins = set()

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)

        if not rows:
            return []

        # Check if first row is a header
        first_row = rows[0]
        start_idx = 0
        asin_col_idx = 0

        # Look for ASIN column header
        for idx, col in enumerate(first_row):
            col_upper = col.strip().upper()
            if col_upper in [v.upper() for v in ASIN_COLUMN_VARIATIONS]:
                asin_col_idx = idx
                start_idx = 1  # Skip header row
                break
        else:
            # No header found - check if first value looks like an ASIN
            if first_row and len(first_row[0].strip()) == 10 and first_row[0].strip().isalnum():
                start_idx = 0  # Include first row as data
            else:
                start_idx = 1  # Assume it's a non-standard header

        # Extract ASINs
        for row in rows[start_idx:]:
            if row and len(row) > asin_col_idx:
                asin = row[asin_col_idx].strip()
                if asin and len(asin) == 10:  # Standard ASIN length
                    asins.add(asin.upper())

    return list(asins)


def find_asin_column(columns: List[str]) -> Optional[str]:
    """
    Find the ASIN column name from a list of column names.

    Args:
        columns: List of column names from the dataframe.

    Returns:
        The matching column name, or None if not found.
    """
    columns_upper = {col.upper(): col for col in columns}

    for variation in ASIN_COLUMN_VARIATIONS:
        if variation.upper() in columns_upper:
            return columns_upper[variation.upper()]

    return None


def trim_bulk_file(
    bulk_file_path: str,
    asin_list: List[str],
    output_path: str,
    chunk_size: int = 50000
) -> Dict[str, Any]:
    """
    Trim a large Amazon Ads bulk export file by filtering to specified ASINs.

    Args:
        bulk_file_path: Path to the input bulk file (.xlsx or .csv).
        asin_list: List of ASINs to keep in the output.
        output_path: Path for the trimmed output file.
        chunk_size: Number of rows to process at a time (for memory efficiency).

    Returns:
        Dictionary with stats:
        - original_rows: Total rows in original file
        - filtered_rows: Rows in output file
        - original_size_mb: Original file size in MB
        - output_size_mb: Output file size in MB
        - size_reduction_percent: Percentage reduction in file size
        - asin_column: Name of the ASIN column used for filtering
    """
    bulk_path = Path(bulk_file_path)
    output_path = Path(output_path)

    if not bulk_path.exists():
        raise FileNotFoundError(f"Bulk file not found: {bulk_file_path}")

    # Normalize ASIN list to uppercase for matching
    asin_set = set(asin.upper() for asin in asin_list)

    original_size_mb = bulk_path.stat().st_size / (1024 * 1024)
    file_ext = bulk_path.suffix.lower()

    print(f"Processing: {bulk_path.name}")
    print(f"Original size: {original_size_mb:.2f} MB")
    print(f"Filtering to {len(asin_set)} unique ASINs")
    print("-" * 50)

    stats = {
        'original_rows': 0,
        'filtered_rows': 0,
        'original_size_mb': original_size_mb,
        'output_size_mb': 0,
        'size_reduction_percent': 0,
        'asin_column': None,
        'metadata_rows': 0,
    }

    if file_ext == '.csv':
        stats = _process_csv(bulk_path, output_path, asin_set, chunk_size, stats)
    elif file_ext in ['.xlsx', '.xls']:
        stats = _process_excel(bulk_path, output_path, asin_set, chunk_size, stats)
    else:
        raise ValueError(f"Unsupported file format: {file_ext}. Use .csv or .xlsx")

    # Calculate output size
    if output_path.exists():
        stats['output_size_mb'] = output_path.stat().st_size / (1024 * 1024)
        if stats['original_size_mb'] > 0:
            stats['size_reduction_percent'] = (
                (1 - stats['output_size_mb'] / stats['original_size_mb']) * 100
            )

    # Print summary
    print("-" * 50)
    print("SUMMARY")
    print("-" * 50)
    print(f"ASIN column used: {stats['asin_column']}")
    print(f"Original rows: {stats['original_rows']:,}")
    print(f"Metadata rows kept: {stats['metadata_rows']:,}")
    print(f"Filtered data rows: {stats['filtered_rows'] - stats['metadata_rows']:,}")
    print(f"Total output rows: {stats['filtered_rows']:,}")
    print(f"Original size: {stats['original_size_mb']:.2f} MB")
    print(f"Output size: {stats['output_size_mb']:.2f} MB")
    print(f"Size reduction: {stats['size_reduction_percent']:.1f}%")
    print(f"Output saved to: {output_path}")

    return stats


def _process_csv(
    input_path: Path,
    output_path: Path,
    asin_set: set,
    chunk_size: int,
    stats: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a CSV bulk file."""

    # First pass: count total rows and find ASIN column
    print("Scanning file structure...")

    # Read just the header to find ASIN column
    header_df = pd.read_csv(input_path, nrows=0)
    asin_column = find_asin_column(header_df.columns.tolist())

    if not asin_column:
        raise ValueError(
            f"Could not find ASIN column. Available columns: {header_df.columns.tolist()}"
        )

    stats['asin_column'] = asin_column

    # Count total rows
    total_rows = sum(1 for _ in open(input_path, 'r', encoding='utf-8-sig')) - 1
    stats['original_rows'] = total_rows

    print(f"Found {total_rows:,} data rows")
    print(f"ASIN column: {asin_column}")
    print("Filtering rows...")

    # Process in chunks
    filtered_chunks = []
    rows_processed = 0

    progress = ProgressBar(total=total_rows, description="Filtering rows")

    for chunk in pd.read_csv(
        input_path,
        chunksize=chunk_size,
        dtype=str,
        keep_default_na=False
    ):
        # Normalize ASIN values for comparison
        chunk_asins = chunk[asin_column].str.strip().str.upper()

        # Keep rows where ASIN is in our list OR ASIN is empty (metadata rows)
        mask = chunk_asins.isin(asin_set) | (chunk_asins == '')
        filtered_chunk = chunk[mask]

        # Count metadata rows (empty ASIN)
        metadata_count = (chunk_asins[mask] == '').sum()
        stats['metadata_rows'] += metadata_count

        if not filtered_chunk.empty:
            filtered_chunks.append(filtered_chunk)

        rows_processed += len(chunk)
        progress.update(len(chunk))

    progress.close()

    # Combine and write output
    if filtered_chunks:
        print("Writing output file...")
        result_df = pd.concat(filtered_chunks, ignore_index=True)
        result_df.to_csv(output_path, index=False)
        stats['filtered_rows'] = len(result_df)
    else:
        print("Warning: No matching rows found!")
        # Write empty file with headers
        header_df.to_csv(output_path, index=False)
        stats['filtered_rows'] = 0

    return stats


def _process_excel(
    input_path: Path,
    output_path: Path,
    asin_set: set,
    chunk_size: int,
    stats: Dict[str, Any]
) -> Dict[str, Any]:
    """Process an Excel bulk file."""

    # Find all sheets with ASIN column
    with Spinner("Loading Excel file structure...", style="dots"):
        xl_file = pd.ExcelFile(input_path, engine='openpyxl')

        # Find all sheets with ASIN column
        sheets_with_asin = []
        for sheet in xl_file.sheet_names:
            header_df = pd.read_excel(input_path, sheet_name=sheet, nrows=0, engine='openpyxl')
            asin_col = find_asin_column(header_df.columns.tolist())
            if asin_col:
                sheets_with_asin.append((sheet, asin_col))

    if not sheets_with_asin:
        all_sheets_info = []
        for sheet in xl_file.sheet_names:
            hdr = pd.read_excel(input_path, sheet_name=sheet, nrows=0, engine='openpyxl')
            all_sheets_info.append(f"  - {sheet}: {list(hdr.columns)[:5]}...")
        raise ValueError(
            f"Could not find ASIN column in any sheet.\n"
            f"Sheets found:\n" + "\n".join(all_sheets_info)
        )

    print(f"✓ Found {len(sheets_with_asin)} sheets with ASIN data:")
    for sheet, col in sheets_with_asin:
        print(f"    - {sheet} (column: {col})")

    stats['asin_column'] = sheets_with_asin[0][1]  # Use first for stats

    # Read and combine all sheets with ASIN data
    all_filtered_dfs = []
    total_original = 0

    for sheet_name, asin_column in sheets_with_asin:
        with Spinner(f"Reading '{sheet_name}'...", style="bouncing"):
            df = pd.read_excel(
                input_path,
                sheet_name=sheet_name,
                dtype=str,
                keep_default_na=False,
                engine='openpyxl'
            )

        total_original += len(df)
        print(f"  ✓ {sheet_name}: {len(df):,} rows")

        # Normalize ASIN values for comparison
        df_asins = df[asin_column].str.strip().str.upper()

        # Keep rows where ASIN is in our list OR ASIN is empty (metadata rows)
        mask = df_asins.isin(asin_set) | (df_asins == '')
        filtered_df = df[mask]

        # Count metadata rows
        stats['metadata_rows'] += (df_asins[mask] == '').sum()

        if not filtered_df.empty:
            all_filtered_dfs.append(filtered_df)

    stats['original_rows'] = total_original

    # Combine all filtered data
    if all_filtered_dfs:
        with Spinner("Combining filtered data...", style="dots"):
            combined_df = pd.concat(all_filtered_dfs, ignore_index=True)
        stats['filtered_rows'] = len(combined_df)
        print(f"✓ Combined: {len(combined_df):,} rows from {len(all_filtered_dfs)} sheets")
    else:
        print("Warning: No matching rows found!")
        combined_df = pd.DataFrame()
        stats['filtered_rows'] = 0

    # Write output - use CSV if output path ends with .csv, otherwise Excel
    output_ext = output_path.suffix.lower()
    with Spinner("Writing output file...", style="dots"):
        if output_ext == '.csv':
            combined_df.to_csv(output_path, index=False)
        else:
            combined_df.to_excel(output_path, index=False, engine='openpyxl')

    print(f"✓ Output saved")

    return stats


def main():
    """Command line interface for bulk_trimmer."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Trim Amazon Ads bulk export files by ASIN list.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bulk_trimmer.py bulk_export.csv asins.csv output.csv
  python bulk_trimmer.py campaign_data.xlsx my_asins.csv trimmed_data.xlsx
        """
    )

    parser.add_argument(
        'bulk_file',
        help='Path to the bulk export file (.csv or .xlsx)'
    )
    parser.add_argument(
        'asin_file',
        help='Path to CSV file containing ASINs to keep'
    )
    parser.add_argument(
        'output_file',
        help='Path for the trimmed output file'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=50000,
        help='Rows to process at a time (default: 50000)'
    )

    args = parser.parse_args()

    # Load ASIN list
    print(f"Loading ASIN list from: {args.asin_file}")
    asin_list = load_asin_list_from_csv(args.asin_file)
    print(f"Loaded {len(asin_list)} unique ASINs")
    print()

    # Process bulk file
    try:
        stats = trim_bulk_file(
            args.bulk_file,
            asin_list,
            args.output_file,
            chunk_size=args.chunk_size
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
