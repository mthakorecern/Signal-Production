#!/usr/bin/env python3

import argparse
import csv
import glob
from pathlib import Path

DEFAULT_GRIDPACK_DIR = "/cvmfs/cms.cern.ch/phys_generator/gridpacks/RunIII/13p6TeV/slc7_amd64_gcc10/MadGraph5_aMCatNLO/GF_HH_Spin0"


def read_masses(path):
    masses = []
    with Path(path).open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            masses.append(int(line))
    return masses


def make_request_name(
    dataset_name,
):
    short_name = dataset_name.split(
        "_Tune",
        1,
    )[0]
    return f"{short_name}_Run3Summer24"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--masses",
        default="mass_points.txt",
    )
    parser.add_argument(
        "--dataset-template",
        required=True,
        help=(
            "Example: "
            "GluGluRadiontoHHto2B2VTo2L2Nu_M-{XYZ}_TuneCP5_13p6TeV_madgraph-pythia8"
        ),
    )
    parser.add_argument(
        "--gridpack-dir",
        default=DEFAULT_GRIDPACK_DIR,
    )
    parser.add_argument(
        "--fragment-template",
        default="fragment_template.py",
    )
    parser.add_argument(
        "--fragment-dir",
        default="fragments",
    )
    parser.add_argument(
        "--output",
        default="campaign.csv",
    )
    args = parser.parse_args()
    if "{XYZ}" not in args.dataset_template:
        raise RuntimeError("Dataset template must contain {XYZ}")

    masses = read_masses(args.masses)
    template = Path(args.fragment_template).read_text()

    if "__GRIDPACK__" not in template:
        raise RuntimeError("Fragment template must contain __GRIDPACK__")

    fragment_dir = Path(args.fragment_dir).resolve()
    fragment_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = []

    for mass in masses:
        dataset_name = args.dataset_template.replace(
            "{XYZ}",
            str(mass),
        )
        gridpack_pattern = str(
            Path(args.gridpack_dir) / (f"Radion_hh_narrow_M{mass}_" "*_tarball.tar.xz")
        )
        matches = sorted(glob.glob(gridpack_pattern))

        if len(matches) != 1:
            raise RuntimeError(
                f"M={mass}: expected exactly one gridpack; "
                f"found {len(matches)}:\n" + "\n".join(matches)
            )
        gridpack_path = str(Path(matches[0]).resolve())
        fragment_path = fragment_dir / f"{dataset_name}.py"
        fragment_path.write_text(
            template.replace(
                "__GRIDPACK__",
                gridpack_path,
            )
        )

        rows.append(
            {
                "Mass": mass,
                "CRAB Request Name": make_request_name(dataset_name),
                "Dataset Name": dataset_name,
                "gridpack Path": gridpack_path,
                "Pythia fragment path": str(fragment_path),
            }
        )

        print(f"M={mass}: {dataset_name}")

    fields = [
        "Mass",
        "CRAB Request Name",
        "Dataset Name",
        "gridpack Path",
        "Pythia fragment path",
    ]

    output_path = Path(args.output).resolve()
    with output_path.open(
        "w",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(rows)
    print()
    print(f"Wrote {len(rows)} entries to:")
    print(output_path)


if __name__ == "__main__":
    main()
