import pandas as pd
from pathlib import Path
from datetime import datetime
import stat
import re

DEP_RE = re.compile(r'\bdepends_on\s*\(\s*"([^"]+)"\s*\)')

def getDependencies(module_file: Path) -> list[str]:
    deps = set()

    try:
        content = module_file.read_text()
        for dep in DEP_RE.findall(content):
            deps.add(dep)

        return sorted(deps)

    except (FileNotFoundError, PermissionError, IsADirectoryError) as e:
        raise RuntimeError(f"Unreadable file: {e}") from e
    
    except UnicodeDecodeError as e:
        raise RuntimeError(f"Encoding issue: {e}") from e
    
    except OSError as e:
        raise RuntimeError(f"Error reading: {e}") from e

def scanModules() -> pd.DataFrame:
    rows = []
    root_path = Path("/hpc/modulefiles")

    for lua in root_path.rglob("*/*.lua"):
        try:
            module = lua.parent.name
            last = lua.name
            version = Path(last).stem.lstrip('.')
            hidden = last.startswith(".")
            st = lua.stat()
            readable_by_others = bool(st.st_mode & stat.S_IROTH)
            public = (not hidden) and readable_by_others
            mod = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
            dependencies = getDependencies(lua)

            rows.append({
                "module_name": module,
                "version": version,
                "public": public,
                "last_mod": mod,
                "dependencies": "; ".join(dependencies)
            })

        except RuntimeError as e:
            print(f"Could not read {lua}: {e}")
            continue

        except OSError as e:
            print(f"Skipping {lua} due to filesystem error: {e}")
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["module_name", "version"], kind="stable").reset_index(drop=True)
    
    return df

def main():
    df = scanModules()
    output = f"module_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="modules", index=False)

        ws = writer.sheets["modules"]
        ws.freeze_panes = "A2" 
        ws.auto_filter.ref = ws.dimensions

    print(f"Wrote {len(df)} rows to {output}")

if __name__ == "__main__":
    main()