"""Create a clean submission archive without secrets or mutable customer data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-dataset', action='store_true', help='Include supplied CSV only when redistribution is permitted')
    args = parser.parse_args()
    output = ROOT / 'submission' / 'ReviewGuard-Final-Year-Project.zip'
    output.parent.mkdir(exist_ok=True)
    excluded = {'node_modules', 'dist', '__pycache__', '.git', '.venv', 'venv', 'artifacts', '.pytest_cache'}
    files = [ROOT / name for name in ('README.md', 'requirements.txt', 'requirements-lock.txt', '.env.example', '.gitignore', 'start-demo.cmd')]
    for folder in ('backend', 'frontend', 'ai_model', 'tests', 'scripts', 'docs'):
        for path in (ROOT / folder).rglob('*'):
            relative = path.relative_to(ROOT)
            if not path.is_file() or excluded.intersection(relative.parts):
                continue
            if 'dataset' in relative.parts and not args.include_dataset:
                continue
            if path.name.startswith('.env') or path.suffix in {'.pyc', '.log', '.db'} or path.name == 'shap_explanation.png':
                continue
            files.append(path)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            if path.exists():
                archive.write(path, Path('ReviewGuard') / path.relative_to(ROOT))
    print(f'Submission archive: {output}')
    print('Model artifacts included. Secrets, databases and virtual environments excluded.')
    print('Dataset included.' if args.include_dataset else 'Dataset excluded; copy your permitted dataset separately for retraining.')


if __name__ == '__main__':
    main()
