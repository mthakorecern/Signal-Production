#!/usr/bin/env python3

import argparse
import csv
import subprocess
import sys
from pathlib import Path

DEFAULT_EXPECTED_FILES = 1000
DEFAULT_USERNAME = "mithakor"
DEFAULT_OUTPUT_TAG = "Private_Run3Summer24_RECO"
DBS_INSTANCE = "prod/phys03"


def run_das(query):
    cmd = [
        "dasgoclient",
        "--query",
        query,
    ]

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:

        raise RuntimeError(
            f"DAS query failed:\n" f"  {' '.join(cmd)}\n\n" f"{result.stderr}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def find_published_datasets(
    primary_dataset,
    username,
    output_tag,
):
    pattern = f"/{primary_dataset}/" f"{username}-{output_tag}-*/USER"
    query = f"dataset dataset={pattern} " f"instance={DBS_INSTANCE}"

    return sorted(set(run_das(query)))


def count_files(dataset):
    query = f"file dataset={dataset} " f"instance={DBS_INSTANCE}"

    files = run_das(query)

    return len(set(files))


def count_events(dataset):

    query = f"summary dataset={dataset} " f"instance={DBS_INSTANCE}"

    cmd = [
        "dasgoclient",
        "--query",
        query,
        "--json",
    ]

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        return None

    try:
        import json

        data = json.loads(result.stdout)

        for entry in data:

            for record in entry.get("summary", []):

                if "nevents" in record:
                    return int(record["nevents"])

    except Exception:
        pass

    return None


def read_campaign(csv_path):

    rows = []

    with open(
        csv_path,
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        required = {
            "Mass",
            "Dataset Name",
        }

        missing = required - set(reader.fieldnames or [])

        if missing:

            raise RuntimeError(
                "Campaign CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for row in reader:

            if not row["Mass"].strip():
                continue

            rows.append(row)

    return rows


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Check that all private RECO datasets "
            "are published in prod/phys03 and have "
            "the expected number of files."
        )
    )
    parser.add_argument(
        "campaign_csv",
        type=Path,
        help="Campaign CSV file",
    )
    parser.add_argument(
        "--expected-files",
        type=int,
        default=DEFAULT_EXPECTED_FILES,
        help=(
            "Expected number of files per dataset "
            f"(default: {DEFAULT_EXPECTED_FILES})"
        ),
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help=("CRAB username " f"(default: {DEFAULT_USERNAME})"),
    )
    parser.add_argument(
        "--output-tag",
        default=DEFAULT_OUTPUT_TAG,
        help=("CRAB outputDatasetTag " f"(default: {DEFAULT_OUTPUT_TAG})"),
    )
    parser.add_argument(
        "--check-events",
        action="store_true",
        help="Also query total events",
    )

    args = parser.parse_args()

    rows = read_campaign(args.campaign_csv)
    print()
    print("RECO publication check")
    print(
        f"{'Mass':>6}  "
        f"{'Published':>10}  "
        f"{'Files':>8}  "
        f"{'Expected':>8}  "
        f"{'Status':>12}  "
        f"Dataset"
    )

    failures = []
    good_datasets = {}
    for row in rows:
        mass = int(row["Mass"])
        primary_dataset = row["Dataset Name"].strip()
        try:

            datasets = find_published_datasets(
                primary_dataset,
                args.username,
                args.output_tag,
            )

        except Exception as exc:

            print(
                f"{mass:6d}  "
                f"{'ERROR':>10}  "
                f"{'-':>8}  "
                f"{args.expected_files:8d}  "
                f"{'DAS ERROR':>12}  "
                f"{exc}"
            )

            failures.append(mass)

            continue

        if len(datasets) == 0:

            print(
                f"{mass:6d}  "
                f"{'NO':>10}  "
                f"{0:8d}  "
                f"{args.expected_files:8d}  "
                f"{'MISSING':>12}  "
                f"{primary_dataset}"
            )

            failures.append(mass)

            continue

        if len(datasets) > 1:

            print(
                f"{mass:6d}  "
                f"{'YES':>10}  "
                f"{'-':>8}  "
                f"{args.expected_files:8d}  "
                f"{'MULTIPLE':>12}  "
                f"{len(datasets)} datasets found"
            )

            for dataset in datasets:
                nfiles = count_files(dataset)
                print(
                    f"{'':6}  "
                    f"{'':10}  "
                    f"{nfiles:8d}  "
                    f"{'':8}  "
                    f"{'':12}  "
                    f"{dataset}"
                )
            failures.append(mass)
            continue
        dataset = datasets[0]
        try:
            nfiles = count_files(dataset)
        except Exception as exc:
            print(
                f"{mass:6d}  "
                f"{'YES':>10}  "
                f"{'-':>8}  "
                f"{args.expected_files:8d}  "
                f"{'DAS ERROR':>12}  "
                f"{dataset}"
            )
            failures.append(mass)
            continue

        if nfiles == args.expected_files:
            status = "OK"
            good_datasets[mass] = dataset
        elif nfiles < args.expected_files:
            status = "INCOMPLETE"
            failures.append(mass)
        else:
            status = "TOO MANY"
            failures.append(mass)

        print(
            f"{mass:6d}  "
            f"{'YES':>10}  "
            f"{nfiles:8d}  "
            f"{args.expected_files:8d}  "
            f"{status:>12}  "
            f"{dataset}"
        )

        if args.check_events:
            nevents = count_events(dataset)
            print(f"{'':6}  " f"{'Events:':>10}  " f"{str(nevents):>8}")

    print(f"Total mass points : {len(rows)}")
    print(f"Ready             : {len(good_datasets)}")
    print(f"Not ready         : {len(failures)}")

    if failures:
        print()
        print("Mass points NOT ready:")
        print(" ".join(str(mass) for mass in failures))
        print()
        print(
            "MiniAOD/NanoAOD production should NOT " "be submitted for all masses yet."
        )
        sys.exit(1)

    print()
    print(
        "All RECO datasets are published and "
        f"contain exactly {args.expected_files} files."
    )
    print("Ready for MiniAOD/NanoAOD production.")
    sys.exit(0)


if __name__ == "__main__":
    main()
