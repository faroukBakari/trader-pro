"""Contract cache inspection tool with CLI table output.

Usage:
    poetry run python scripts/inspect_contract_cache.py
    poetry run python scripts/inspect_contract_cache.py --format json
    poetry run python scripts/inspect_contract_cache.py --symbol AAPL
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path

# Rich table formatting (optional - graceful fallback to plain text)
try:
    from rich.console import Console
    from rich.table import Table

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Import from authoritative source
from trading_api.providers.tws.contract_tracker import get_cache_path


def get_connection(db_path: str) -> sqlite3.Connection:
    """Connect to SQLite cache."""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Cache not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_stats(conn: sqlite3.Connection) -> dict:
    """Gather cache statistics."""
    cursor = conn.execute("SELECT COUNT(*) as total FROM contract_descriptions")
    total = cursor.fetchone()["total"]

    cursor = conn.execute(
        """
        SELECT primary_exchange, COUNT(*) as count
        FROM contract_descriptions
        GROUP BY primary_exchange
        ORDER BY count DESC
    """
    )
    exchanges = {row["primary_exchange"]: row["count"] for row in cursor}

    cursor = conn.execute(
        """
        SELECT sec_type, COUNT(*) as count
        FROM contract_descriptions
        GROUP BY sec_type
        ORDER BY count DESC
    """
    )
    sec_types = {row["sec_type"]: row["count"] for row in cursor}

    return {
        "total": total,
        "exchanges": exchanges,
        "sec_types": sec_types,
    }


def get_latest_records(conn: sqlite3.Connection, limit: int = 10):
    """Get most recently added contracts."""
    cursor = conn.execute(
        f"""
        SELECT con_id, symbol, sec_type, primary_exchange,
               datetime(created_at, 'unixepoch') as created,
               description
        FROM contract_descriptions
        ORDER BY created_at DESC
        LIMIT {limit}
    """
    )
    return [dict(row) for row in cursor.fetchall()]


def search_by_symbol(conn: sqlite3.Connection, symbol: str):
    """Search contracts by symbol prefix."""
    cursor = conn.execute(
        """
        SELECT con_id, symbol, sec_type, primary_exchange,
               datetime(created_at, 'unixepoch') as created,
               description
        FROM contract_descriptions
        WHERE symbol LIKE ? || '%'
        ORDER BY symbol
    """,
        (symbol.upper(),),
    )
    return [dict(row) for row in cursor.fetchall()]


def print_stats_table(stats: dict, db_path: str):
    """Print statistics in table format."""
    if HAS_RICH:
        console = Console()

        # Header
        console.print("\n[bold cyan]📊 Contract Cache Statistics[/bold cyan]")
        console.print(f"[dim]Database: {db_path}[/dim]\n")

        # Total count
        console.print(f"[bold]Total Contracts:[/bold] {stats['total']:,}")

        # Exchanges table
        table = Table(
            title="Top Exchanges", show_header=True, header_style="bold magenta"
        )
        table.add_column("Exchange", style="cyan")
        table.add_column("Count", justify="right", style="green")
        for exchange, count in list(stats["exchanges"].items())[:10]:
            table.add_row(exchange, str(count))
        console.print(table)

        # Security types table
        table = Table(
            title="Security Types", show_header=True, header_style="bold magenta"
        )
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right", style="green")
        for sec_type, count in stats["sec_types"].items():
            table.add_row(sec_type, str(count))
        console.print(table)
    else:
        # Plain text fallback
        print("\n" + "=" * 60)
        print("📊 CONTRACT CACHE STATISTICS")
        print("=" * 60)
        print(f"Database: {db_path}")
        print(f"\nTotal Contracts: {stats['total']:,}")

        print("\n--- Top Exchanges ---")
        for exchange, count in list(stats["exchanges"].items())[:10]:
            print(f"{exchange:20} {count:>6,}")

        print("\n--- Security Types ---")
        for sec_type, count in stats["sec_types"].items():
            print(f"{sec_type:20} {count:>6,}")
        print("=" * 60)


def print_records_table(records, title: str):
    """Print contract records in table format."""
    if not records:
        print(f"\n{title}: No records found")
        return

    if HAS_RICH:
        console = Console()
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("ConID", style="dim")
        table.add_column("Symbol", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Exchange", style="green")
        table.add_column("Created", style="dim")
        table.add_column("Description", style="white", no_wrap=False)

        for row in records:
            table.add_row(
                str(row["con_id"]),
                row["symbol"],
                row["sec_type"],
                row["primary_exchange"],
                row.get("created", "N/A")[:19] if "created" in row.keys() else "N/A",
                (row.get("description") or "")[:40],
            )
        console.print(table)
    else:
        # Plain text fallback
        print(f"\n{title}")
        print("-" * 100)
        print(
            f"{'ConID':>10} {'Symbol':10} {'Type':6} {'Exchange':12} {'Created':20} {'Description':30}"
        )
        print("-" * 100)
        for row in records:
            desc = (row.get("description") or "")[:30]
            created = (
                row.get("created", "N/A")[:19] if "created" in row.keys() else "N/A"
            )
            print(
                f"{row['con_id']:>10} {row['symbol']:10} {row['sec_type']:6} {row['primary_exchange']:12} {created:20} {desc:30}"
            )


def main():
    parser = argparse.ArgumentParser(description="Inspect contract cache")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--symbol", help="Search by symbol prefix")
    parser.add_argument(
        "--latest", type=int, default=10, help="Number of latest records (default: 10)"
    )
    args = parser.parse_args()

    db_path = get_cache_path()

    try:
        conn = get_connection(db_path)

        if args.symbol:
            # Symbol search
            records = search_by_symbol(conn, args.symbol)
            if args.format == "json":
                print(json.dumps([dict(r) for r in records], indent=2))
            else:
                print_records_table(records, f"Contracts matching '{args.symbol}'")
        else:
            # Full stats + latest
            stats = get_stats(conn)
            latest = get_latest_records(conn, args.latest)

            if args.format == "json":
                output = {
                    "database": db_path,
                    "stats": stats,
                    "latest_records": [dict(r) for r in latest],
                }
                print(json.dumps(output, indent=2))
            else:
                print_stats_table(stats, db_path)
                print_records_table(latest, f"\n📅 Latest {args.latest} Contracts")

        conn.close()

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print(f"\n💡 The cache is created after first use of the app.")
        print(f"   Start the backend and search for symbols to populate the cache.")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
