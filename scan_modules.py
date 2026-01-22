import pandas as pd
from pathlib import Path

root_path = Path("/hpc/modulefiles")

def scanModules() -> pd.DataFrame:
    rows = []

    for lua in root_path.rglob("*/*.lua"):
        parts = lua.parts[1:]
        module = parts[2]
        print(module)
        version = Path(parts[3]).stem.lstrip('.')
        print(version)
        hidden = parts[3].startswith(".")
        print(hidden)
        st = lua.stat()
        print(st)
        break

def main():
    scanModules()

if __name__ == "__main__":
    main()