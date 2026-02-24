import csv
from collections import Counter

CSV_PATH = "data/biometric_auth.csv"

def analyze(path):
    counts = Counter()
    samples = {}
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, start=1):
            n = len(row)
            counts[n] += 1
            if n not in samples:
                samples[n] = (i, row)
    return counts, samples

if __name__ == '__main__':
    counts, samples = analyze(CSV_PATH)
    print('Column counts distribution:')
    for cols, cnt in sorted(counts.items(), reverse=True):
        print(f'  {cols} columns: {cnt} rows')
    print('\nSample rows (first occurrence per column-count):')
    for cols, (lineno, row) in sorted(samples.items()):
        print(f'--- {cols} columns (line {lineno}):')
        print(row)
