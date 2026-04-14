# SciducTainer
Minimal example (template) repo which includes files to interface with Sciduct job service.

This one happens to only depend on Python, with it's **top-level** (E.g. only things in import statments which are **not** in the Python standard library) dependencies and Python version specified in [environment.yml](environment.yml).
That should have any dependencies added (with pinned versions) to be able to run without containerization.
E.g.

```bash
micromamba env create --file environment.yml
micromamba activate app_env001
./src/app_script001.py --name Sue
# Sue's age is 33.
```

The [example app script](src/app_script001.py) shows a way to provide parameters via a config file (E.g. app_script001_config.json). An example file is provided as a starter.
E.g.
```bash
cp src/app_script001_config_example.json app_script001_config.json
```
Those will be overridden by any explicit parameters passed in on the command line.

To use this, just click "Use this template". Create new repository with a name relevant for your app(s).
Then change file and app names as appropriate (E.g. [src/app_script001.py](src/app_script001.py) and in [apps.scif](apps.scif)).

This system uses Github Actions to build and publish a container, triggered by a git tag push of the form `v<major>.<minor>.<patch>` (See: [Semantic Versioning](https://semver.org/) for a quick explanation of what those mean).

E.g.
```bash
git add -u
git commit -m "useful commit message"
git pull --rebase && git push
git tag v0.1.1
git push origin v0.1.1
```

To enable Github Actions to build and publish this to the Github Container Resgistry (GHCR), someone will need to create an authentication [token](https://github.com/settings/tokens) with via their Github account having "repo" and "write:packages" permissions. If a private repo needs to be accessed, a "GH_TOKEN" with "repo" priveleges also needs to be added.

The tokens and username needs to be saved as a repository secret (in "https://github.com/user-or-org-name/repo-name/settings/secrets/actions"), with names matching the ones in [.github/workflows/build_docker.yml](.github/workflows/build_docker.yml)


Make sure to change your container image name to match your repo name (E.g. [here](https://github.com/NSSAC/SciducTainer/blob/a69540ac1a551f12f9d9748d11e28240096bd582/.github/workflows/build_docker.yml#L30)).

## Pulling and Running (testing) the Container via Apptainer (Docker bootstrap)
**Note: adjust names to match your actual container and repo name, NOT SciducTainer.**
```bash
git clone git@github.com:NSSAC/SciducTainer.git
cd SciducTainer
# module load apptainer
apptainer pull docker://ghcr.io/nssac/sciductainer:0.1.0
mkdir -p data
apptainer run --bind=data:/scif/data sciductainer_0.1.0.sif run app001 --age 42
# [app001] executing /bin/bash /scif/apps/app001/scif/runscript --age 42
# Running app_script001.py --outdir /scif/data/app001 --age 42
# Bob's age is 42.
```

If you want to also test changes to script files in the repository, and have the container use those, you can additionally `--bind` your local repo files directory in ("mounting" over the read-only copy of that in the container image).
E.g.

```bash
# Change to 'age: int = 34' in src/app_script001.py
apptainer run --bind=data:/scif/data,src:/scif/apps/app001/lib sciductainer_0.1.5.sif run app001
```

Specifically with the app_dtd app you need to bind in the rivanna path to the populations like
```bash
apptainer run --bind=data:/scif/data --bind=src:/scif/apps/app_dtd/bin --bind=/project/bii_nssac/production/detailed_populations/ver_2_4_0/:/scif/data/pop digitaltwindemographics_latest.sif run app_dtd -- --us-state md
```

With some of the "pre-canned" polygons
```bash
apptainer run --bind=data:/scif/data --bind=src:/scif/apps/app_dtd/bin --bind=/project/bii_nssac/production/detailed_populations/ver_2_4_0/:/scif/data/pop digitaltwindemographics_latest.sif run app_dtd -- --us-state md --polygon HSA
```


Data sources:

Wastewater boundaries:  WasteWaterScan.org
National DMAS: https://services.arcgis.com/AgwDJMQH12AGieWa/ArcGIS/rest/services/DMA/FeatureServer/0 (maybe)
HSA boundaries:  https://data.dartmouthatlas.org/supplemental/
HRR boundaries:  https://data.dartmouthatlas.org/supplemental/

SOCP codes from:  https://api.census.gov/data/2022/acs/acs5/pums/variables/SOCP.json


