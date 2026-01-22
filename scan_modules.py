import pandas as pd
from pathlib import Path
from datetime import datetime
import stat

root_path = Path("/hpc/modulefiles")

def scanModules() -> pd.DataFrame:
    rows = []

    for lua in root_path.rglob("*/*.lua"):
        parts = lua.parts[1:]
        module = parts[2]
        version = Path(parts[3]).stem.lstrip('.')
        hidden = parts[3].startswith(".")
        print(hidden)
        st = lua.stat()
        readable_by_others = bool(st.st_mode & stat.S_IROTH)
        print(readable_by_others)
        print(datetime.fromtimestamp(st.st_mtime))
        print(datetime.fromtimestamp(st.st_atime))
        break

def main():
    scanModules()

if __name__ == "__main__":
    main()