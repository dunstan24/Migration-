import argparse
import pandas as pd
import os
import sys

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

def parse_year(val):
    val = str(val).strip()
    if len(val) == 6 and val[3] == "-":
        mon = val[:3].lower()
        yy = val[4:6]
        if mon in MONTH_MAP and yy.isdigit():
            return 2000 + int(yy)
    if "/" in val:
        for p in val.split("/"):
            if len(p) == 4 and p.isdigit():
                return int(p)
    return None

def split_by_year(input_file, output_dir):
    if not os.path.exists(input_file):
        print("File tidak ditemukan:", input_file)
        sys.exit(1)
    os.makedirs(output_dir, exist_ok=True)
    print("Membaca:", input_file)
    df = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    df = df[df["As At Month"] != "As At Month"].copy()
    df = df[df["As At Month"].notna()].copy()
    print("Total baris:", len(df))
    print("Sample:", df["As At Month"].iloc[:3].tolist())
    df["_year"] = df["As At Month"].apply(parse_year)
    df = df[df["_year"].notna()].copy()
    df["_year"] = df["_year"].astype(int)
    years = sorted(df["_year"].unique())
    print("Tahun ditemukan:", years)
    for year in years:
        out = df[df["_year"] == year].drop(columns=["_year"])
        path = os.path.join(output_dir, f"EOI_{year}.csv")
        out.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"EOI_{year}.csv -> {len(out):,} baris")
    print("Selesai!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="./output")
    args = parser.parse_args()
    split_by_year(args.input, args.output_dir)