"""Generate the remaining balanced plots sequentially, then verify results.

Run from the repository root: python utiles/finish_results.py
The completed toy plot is retained. Adder finishes before Log2 starts.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    for name in ('adder', 'log2'):
        subprocess.run([sys.executable, '-u', str(ROOT/'utiles/plot_result.py'), name],
                       cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT/'utiles/document_results.py')], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT/'utiles/verify_results.py')], cwd=ROOT, check=True)
