from pathlib import Path

CLEANING_DIR = Path(__file__).parent / "cleaning"


def main() -> None:
    originals: dict[str, int] = {}
    cleaned: dict[str, int] = {}

    for path in CLEANING_DIR.iterdir():
        if not path.is_file() or path.suffix != ".html":
            continue
        name = path.stem
        if name.endswith("-original"):
            uuid = name.removesuffix("-original")
            originals[uuid] = path.stat().st_size
        elif name.endswith("-cleaned"):
            uuid = name.removesuffix("-cleaned")
            cleaned[uuid] = path.stat().st_size

    uuids = sorted(set(originals) & set(cleaned))
    if not uuids:
        print("No matching original/cleaned pairs found.")
        return

    total_original = 0
    total_cleaned = 0
    total_factor = 0.0

    print(f"{'uuid':<38} {'original':>10} {'cleaned':>10} {'factor':>8}")
    print("-" * 70)

    for uuid in uuids:
        orig = originals[uuid]
        clean = cleaned[uuid]
        factor = clean / orig if orig else 0.0

        total_original += orig
        total_cleaned += clean
        total_factor += factor

        print(f"{uuid:<38} {orig:>10,} {clean:>10,} {factor:>7.2%}")

    n = len(uuids)
    print("-" * 70)
    print(
        f"{'AVERAGE':<38} "
        f"{total_original / n:>10,.0f} "
        f"{total_cleaned / n:>10,.0f} "
        f"{total_factor / n:>7.2%}"
    )

    only_original = sorted(set(originals) - set(cleaned))
    only_cleaned = sorted(set(cleaned) - set(originals))
    if only_original or only_cleaned:
        print()
        if only_original:
            print(f"Missing cleaned ({len(only_original)}): {', '.join(only_original)}")
        if only_cleaned:
            print(f"Missing original ({len(only_cleaned)}): {', '.join(only_cleaned)}")


if __name__ == "__main__":
    main()
