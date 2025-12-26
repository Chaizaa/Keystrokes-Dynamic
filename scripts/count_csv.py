import csv

with open('data/biometric_auth.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    
print(f'Total rows in CSV: {len(rows)}')

users = set()
for row in rows:
    users.add(row['username'])

print(f'Unique users: {len(users)}')
print(f'Users: {list(users)}')
