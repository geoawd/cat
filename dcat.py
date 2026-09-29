"""
Maps a portal dataset record (as parsed from data/*.yaml) to a DCAT-shaped
JSON-LD record.

DCAT was chosen because it's what the UK Government Data Standards Authority
recommends for describing datasets/data services in a catalogue -- it's what
data.gov.uk already uses, and it builds on Dublin Core, so it covers a
report or document just as naturally as a spatial layer. See:
https://www.gov.uk/government/publications/recommended-open-standards-for-government/using-metadata-to-describe-data-assets-in-a-data-catalogue

Scope note: this is a practical starting point, not a certified DCAT-AP-UK
or GEMINI export.
  - The dct:/dcat:/foaf:/vcard: terms below are real DCAT/Dublin Core terms
    and cover the common ground between a dataset and a non-spatial report.
  - geometry_type and the project CRS are exposed as a light "gemini:"
    extension for spatial layers specifically -- useful as a pointer, not a
    substitute for real UK GEMINI 2.3 elements.
  - A conformant UK GEMINI 2.3 / ISO 19115 export is a separate, larger
    piece of work: GEMINI is XML (not JSON-LD), and needs fields this
    starter doesn't collect yet -- a bounding box, a proper CRS codelist
    entry, an INSPIRE theme, lineage, resource constraints, maintenance
    frequency. Worth building as its own module (e.g. gemini_xml.py) once
    the schema needs to go that far.
"""

CONTEXT = {
    "dct": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "vcard": "http://www.w3.org/2006/vcard/ns#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "gemini": "http://www.gov.uk/gemini/2.3/",
}


def _distributions(ds):
    items = []
    if ds.get("service_url"):
        items.append({
            "@type": "dcat:Distribution",
            "dct:title": "Live feature/map service",
            "dcat:accessURL": ds["service_url"],
        })
    for link in ds.get("external_links") or []:
        items.append({
            "@type": "dcat:Distribution",
            "dct:title": link.get("label"),
            "dcat:accessURL": link.get("url"),
        })
    return items


def dataset_to_dcat(ds, record_url, project_epsg):
    """A single dataset -> a dcat:Dataset JSON-LD record."""
    record = {
        "@context": CONTEXT,
        "@id": record_url,
        "@type": "dcat:Dataset",
        "dct:identifier": ds.get("id"),
        "dct:title": ds.get("title"),
        "dct:abstract": ds.get("summary"),
        "dct:description": ds.get("description"),  # raw markdown source
        "dct:issued": ds.get("date_published"),
        "dct:license": ds.get("license"),
        "dct:isPartOf": ds.get("group"),
        "dct:bibliographicCitation": ds.get("citation"),
        "dcat:keyword": ds.get("tags") or [],
        "dcat:distribution": _distributions(ds),
    }

    if ds.get("author"):
        record["dct:creator"] = {"@type": "foaf:Agent", "foaf:name": ds["author"]}
    if ds.get("contact"):
        record["dcat:contactPoint"] = {
            "@type": "vcard:Kind",
            "vcard:hasEmail": f"mailto:{ds['contact']}",
        }
    if ds.get("doi"):
        record["owl:sameAs"] = f"https://doi.org/{ds['doi']}"
    if ds.get("geometry_type"):
        record["gemini:geometryType"] = ds["geometry_type"]
    if ds.get("service_url"):
        record["gemini:spatialReferenceSystem"] = project_epsg

    # Drop empty/unset fields so the JSON stays readable.
    return {k: v for k, v in record.items() if v not in (None, "", [], {})}


def catalog_to_dcat(datasets, catalog_url, site_title, record_urls, project_epsg):
    """The whole catalog -> a dcat:Catalog wrapping every dcat:Dataset."""
    return {
        "@context": CONTEXT,
        "@id": catalog_url,
        "@type": "dcat:Catalog",
        "dct:title": site_title,
        "dcat:dataset": [
            dataset_to_dcat(ds, record_urls[ds["id"]], project_epsg)
            for ds in datasets
        ],
    }
