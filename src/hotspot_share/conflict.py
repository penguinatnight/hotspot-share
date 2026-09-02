import os
import re
from pathlib import Path

def split_filename_and_ext(filename: str) -> tuple[str, str]:
    """Splits a filename into base stem and extension, correctly handling compound extensions like .tar.gz."""
    lower = filename.lower()
    for compound in (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst"):
        if lower.endswith(compound):
            return filename[:-len(compound)], filename[-len(compound):]
    p = Path(filename)
    return p.stem, p.suffix

def resolve_filename_conflict(target_path: Path, strategy: str = "rename") -> Path:
    """
    Resolves file naming conflicts according to the specified strategy.
    
    Strategies:
      - 'overwrite': Returns target_path directly.
      - 'skip': Returns target_path if it exists (caller checks file existence & size).
      - 'rename' (default): Generates 'name (1).ext', 'name (2).ext', etc. if target_path exists.
    """
    strategy = (strategy or "rename").lower().strip()
    if strategy == "overwrite":
        return target_path

    if not target_path.exists():
        return target_path

    if strategy == "skip":
        return target_path

    # Strategy 'rename'
    parent = target_path.parent
    name = target_path.name
    stem, ext = split_filename_and_ext(name)

    # Check if stem already ends with (N)
    m = re.match(r"^(.*?)\s*\((\d+)\)$", stem)
    if m:
        base_stem = m.group(1).rstrip()
        counter = int(m.group(2)) + 1
    else:
        base_stem = stem
        counter = 1

    candidate = parent / f"{base_stem} ({counter}){ext}"
    while candidate.exists():
        counter += 1
        candidate = parent / f"{base_stem} ({counter}){ext}"

    return candidate
