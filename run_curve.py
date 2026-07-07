import csv
from src.bootstrap import bootstrap_curve
from src.curve import Curve

quotes = []

with open("data/processed/boe_ois_quotes.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        quotes.append((float(row["tenor_years"]), float(row["rate"])))

print("Bootstrapping discount factors from quotes...")
dfs = bootstrap_curve(quotes)
curves = Curve(dfs)

print("\nBootstrapped discount factors and zero rates:")
for tenor, D in dfs.items():
    z = curves.zero_rate(tenor)
    print(f"  {tenor}: {D} (zero rate: {z})")