"""Package an explicit source allowlist; never include local sessions."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]

def main():
    destination=ROOT/'dist'/'brightspace-facultad-mcp-0.1.0-source.zip'
    destination.parent.mkdir(exist_ok=True)
    files=[ROOT/name for name in ['README.md','INSTALL_WITH_AI.md','.gitignore','LICENSE','pyproject.toml','install.sh','install.ps1',
                                 'requirements.lock','requirements-dev.lock','requirements-build.lock']]
    for folder in ['src','scripts','tests','docs']:
        files.extend(path for path in (ROOT/folder).rglob('*')
                     if path.is_file() and path.suffix in {'.py','.md','.txt'} and '__pycache__' not in path.parts)
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path,Path('brightspace-facultad-mcp')/path.relative_to(ROOT))
    print(destination)

if __name__=='__main__':
    main()
