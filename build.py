"""
Static site build: renders Jinja2 templates + writes DCAT-shaped JSON
endpoints using config.yaml + data/*.yaml into dist/. Run: python build.py
"""
import json
import shutil
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

import dcat

ROOT = Path(__file__).parent
DIST = ROOT / "dist"


def load_config():
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def load_datasets():
    """
    Loads every *.yaml file in data/. Each file is either:
      - a plain list of dataset dicts (no grouping), or
      - a dict with "group: <label>" and "datasets: [...]"
    A dataset can set its own "group" to override the file-level one
    (e.g. a theme layer living in a partner's file).

    A dataset's "id" becomes its URL path segment (/catalogue/<id>/) and
    JSON filename, so it must be URL/filesystem safe -- a slug or a UUID
    both work fine.
    """
    datasets = []
    seen_ids = {}

    for path in sorted((ROOT / "data").glob("*.yaml")):
        content = yaml.safe_load(path.read_text())
        if isinstance(content, list):
            file_group, entries = None, content
        elif isinstance(content, dict):
            file_group, entries = content.get("group"), content.get("datasets", [])
        else:
            continue

        for ds in entries:
            ds.setdefault("group", file_group or "Other")
            if ds["id"] in seen_ids:
                raise ValueError(
                    f"Duplicate dataset id '{ds['id']}' in {path.name} "
                    f"(already defined in {seen_ids[ds['id']]})"
                )
            seen_ids[ds["id"]] = path.name
            datasets.append(ds)

    return datasets


def main():
    config = load_config()
    datasets = load_datasets()
    datasets_sorted = sorted(datasets, key=lambda d: (d["group"], d["title"]))

    # Markdown "description" -> HTML, rendered once, used by dataset.html.
    # metadata.json keeps the raw markdown source instead (see dcat.py) so
    # machine consumers can render it however they like.
    for ds in datasets_sorted:
        ds["description_html"] = markdown.markdown(
            ds.get("description", ""), extensions=["extra"]
        )

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    env = Environment(loader=FileSystemLoader(ROOT / "templates"))
    base_url = config["site"]["base_url"]
    canonical = (config["site"].get("canonical_url") or "").rstrip("/")
    common = {
        "site": config["site"],
        "project": config["project"],
        "libraries": config.get("libraries", {}),
        "base_url": base_url,
    }

    # Home / catalog page (single page, grouped, no pagination)
    (DIST / "index.html").write_text(
        env.get_template("index.html").render(datasets=datasets_sorted, **common)
    )

    # Map page (dataset dropdown covers all layers)
    (DIST / "map.html").write_text(
        env.get_template("map.html").render(datasets=datasets_sorted, **common)
    )

    # One directory per dataset: /catalogue/<id>/index.html + metadata.json
    catalogue_dir = DIST / "catalogue"
    catalogue_dir.mkdir()
    dataset_template = env.get_template("dataset.html")
    record_urls = {
        ds["id"]: f"{canonical}{base_url}catalogue/{ds['id']}/"
        for ds in datasets_sorted
    }

    for ds in datasets_sorted:
        record_dir = catalogue_dir / ds["id"]
        record_dir.mkdir()

        (record_dir / "index.html").write_text(
            dataset_template.render(ds=ds, **common)
        )

        record = dcat.dataset_to_dcat(
            ds, record_urls[ds["id"]], config["project"]["epsg"]
        )
        (record_dir / "metadata.json").write_text(json.dumps(record, indent=2))

    # Whole-catalog endpoint: /catalog.json
    catalog_doc = dcat.catalog_to_dcat(
        datasets_sorted,
        catalog_url=f"{canonical}{base_url}catalog.json",
        site_title=config["site"]["title"],
        record_urls=record_urls,
        project_epsg=config["project"]["epsg"],
    )
    (DIST / "catalog.json").write_text(json.dumps(catalog_doc, indent=2))

    # Static assets
    shutil.copytree(ROOT / "static", DIST / "static")

    print(
        f"Built {2 + len(datasets_sorted) * 2 + 1} files "
        f"({len(datasets_sorted)} datasets) into {DIST}"
    )


if __name__ == "__main__":
    main()
