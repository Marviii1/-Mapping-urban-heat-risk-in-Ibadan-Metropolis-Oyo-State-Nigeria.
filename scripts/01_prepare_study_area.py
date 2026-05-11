from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.boundary import list_state_lgas, prepare_study_area
from src.utils.config import load_yaml, project_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Ibadan metropolitan study boundary.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  # Check what LGA names your shapefile uses before running the full prep:
  python scripts/01_prepare_study_area.py \\
      --boundary data/raw/boundary/nigeria_lgas.shp --list-lgas

  # Full study area preparation:
  python scripts/01_prepare_study_area.py \\
      --boundary data/raw/boundary/nigeria_lgas.shp
""",
    )
    parser.add_argument(
        "--boundary",
        required=True,
        type=Path,
        help="Path to Nigeria LGA boundary shapefile or GeoPackage.",
    )
    parser.add_argument(
        "--config",
        default=Path("config/project_config.yml"),
        type=Path,
        help="Project YAML configuration path.",
    )
    parser.add_argument(
        "--list-lgas",
        action="store_true",
        help=(
            "Print all LGA names found in the shapefile for Oyo State and exit. "
            "Use this to confirm exact name spellings before running the full prep."
        ),
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    cfg = load_yaml(args.config)
    boundary = args.boundary if args.boundary.is_absolute() else project_path(args.boundary)

    if not boundary.exists():
        print(f"ERROR: Boundary file not found: {boundary}")
        return 1

    # ── Diagnostic list mode ─────────────────────────────────────────────────
    if args.list_lgas:
        state = cfg["study_area"]["state_name"]
        print(f"\nAll LGA names in the shapefile for state '{state}':\n")
        try:
            df = list_state_lgas(boundary, state_name=state)
        except Exception as exc:
            print(f"ERROR reading shapefile: {exc}")
            return 1

        if df.empty:
            print(f"  No LGAs found for state '{state}'.")
            print("  Check that the state name in config/project_config.yml matches the shapefile.")
        else:
            # Mark which names match the target LGAs in config
            from src.data.boundary import normalize_name
            targets = {normalize_name(n) for n in cfg["study_area"]["target_lgas"]}
            print(f"  {'Shapefile name':<35}  {'Match?'}")
            print(f"  {'─' * 35}  {'─' * 10}")
            for _, row in df.iterrows():
                matched = "✓ in config" if row["normalized_name"] in targets else ""
                print(f"  {row['source_name']:<35}  {matched}")
            n_matched = sum(1 for _, r in df.iterrows() if r["normalized_name"] in targets)
            print(f"\n  {n_matched} / {len(cfg['study_area']['target_lgas'])} target LGAs matched.")
            missing = [
                n for n in cfg["study_area"]["target_lgas"]
                if normalize_name(n) not in {r["normalized_name"] for _, r in df.iterrows()}
            ]
            if missing:
                print("\n  NOT MATCHED (check spelling):")
                for m in missing:
                    print(f"    - {m}")
        return 0

    # ── Full study area preparation ──────────────────────────────────────────
    sa = cfg["study_area"]
    outputs = prepare_study_area(
        boundary_path=boundary,
        target_lgas=sa["target_lgas"],
        state_name=sa["state_name"],
        projected_crs=cfg["project"]["crs_projected"],
        output_dir=project_path("data/processed/uhi"),
        table_dir=project_path("data/processed/tables"),
        core_lgas=sa.get("core_lgas"),
        periurban_lgas=sa.get("periurban_lgas"),
    )

    print("\nStudy area preparation complete.")
    print(f"  LGA column detected : {outputs.lga_column}")
    print(f"  State column        : {outputs.state_column or 'not found'}")
    if outputs.missing_lgas:
        print(f"  WARNING — missing  : {', '.join(outputs.missing_lgas)}")
        print("  Run --list-lgas to see exact shapefile LGA names.")
    print(f"\n  LGAs GeoPackage     : {outputs.lgas_path}")
    print(f"  Metro boundary      : {outputs.boundary_path}")
    print(f"  LGA table CSV       : {outputs.lga_table_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
