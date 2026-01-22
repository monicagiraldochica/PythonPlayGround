import pandas as pd
from pathlib import Path

def scanModules() -> pd.DataFrame:
    rows = []
    root_path = Path("/hpc/modulefiles")

    for lua in root_path.rglob("*.lua"):
        print(lua)
        break