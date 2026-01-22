import pandas as pd
from pathlib import Path

root_path = Path("/hpc/modulefiles")

def scanModules() -> pd.DataFrame:
    rows = []

    for lua in root_path.rglob("*/*.lua"):
        print(lua)
        break

def main():
    scanModules()

if __name__ == "__main__":
    main()