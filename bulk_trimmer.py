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

# Optional tqdm for progress bars
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

    # Dummy tqdm that just iterates
    class tqdm:
        def __init__(self, iterable=None, total=None, unit=None, desc=None, **kwargs):
            self.iterable = iterable
            self.total = total
            self.n = 0

        def __iter__(self):
            return iter(self.iterable) if self.iterable else iter([])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def update(self, n=1):
            self.n += n
            if self.total:
                print(f"\rProcessing: {self.n:,}/{self.total:,} rows ({100*self.n/self.total:.1f}%)", end='', flush=True)

        def close(self):
            print()  # New line after progress


# Common ASIN column name variations in Amazon Ads bulk exports
ASIN_COLUMN_VARIATIONS = [
    'ASIN',
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

    with tqdm(total=total_rows, unit='rows', desc='Processing') as pbar:
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
            pbar.update(len(chunk))

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

    print("Loading Excel file (this may take a while for large files)...")

    # For very large Excel files, we need to read in chunks
    # First, get the sheet info
    xl_file = pd.ExcelFile(input_path, engine='openpyxl')
    sheet_name = xl_file.sheet_names[0]

    # Read header row
    header_df = pd.read_excel(input_path, sheet_name=sheet_name, nrows=0, engine='openpyxl')
    asin_column = find_asin_column(header_df.columns.tolist())

    if not asin_column:
        raise ValueError(
            f"Could not find ASIN column. Available columns: {header_df.columns.tolist()}"
        )

    stats['asin_column'] = asin_column

    # For Excel, we need to read the whole file (openpyxl doesn't support chunked reading well)
    print(f"ASIN column: {asin_column}")
    print("Reading Excel data...")

    df = pd.read_excel(
        input_path,
        sheet_name=sheet_name,
        dtype=str,
        keep_default_na=False,
        engine='openpyxl'
    )

    stats['original_rows'] = len(df)
    print(f"Found {len(df):,} data rows")
    print("Filtering rows...")

    # Normalize ASIN values for comparison
    df_asins = df[asin_column].str.strip().str.upper()

    # Keep rows where ASIN is in our list OR ASIN is empty (metadata rows)
    mask = df_asins.isin(asin_set) | (df_asins == '')
    filtered_df = df[mask]

    # Count metadata rows
    stats['metadata_rows'] = (df_asins[mask] == '').sum()
    stats['filtered_rows'] = len(filtered_df)

    # Write output
    print("Writing output file...")
    filtered_df.to_excel(output_path, index=False, engine='openpyxl')

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
