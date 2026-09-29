// Reads the config embedded in the page, registers the project CRS with
// proj4/OpenLayers, and loads whichever dataset is selected as a vector
// layer queried directly from its source REST service.

const config = JSON.parse(document.getElementById('portal-config').textContent);

// --- 1. Register the project projection ------------------------------
// Any EPSG code works here as long as proj4def is correct for it.
proj4.defs(config.project.epsg, config.project.proj4def);
ol.proj.proj4.register(proj4);

const projectProjection = new ol.proj.Projection({
  code: config.project.epsg,
  extent: config.project.extent,
  units: 'm',
});

// --- 2. Base map -------------------------------------------------------
// OSM tiles are served in EPSG:3857; OpenLayers reprojects them on the fly
// to match the view's projection. Swap this for a WMTS/XYZ source that
// natively serves the project CRS if reprojected tiles aren't sharp enough.
const baseLayer = new ol.layer.Tile({
  source: new ol.source.OSM(),
});

const view = new ol.View({
  projection: projectProjection,
  center: config.project.center,
  zoom: config.project.zoom,
  extent: config.project.extent,
});

const map = new ol.Map({
  target: 'map',
  layers: [baseLayer],
  view: view,
});

// --- 3. REST vector layer ----------------------------------------------
// Numeric EPSG code for the outSR query param (Esri REST wants e.g. 27700,
// not the "EPSG:" prefix).
const outSR = config.project.epsg.replace('EPSG:', '');

let activeLayer = null;

function buildQueryUrl(serviceUrl) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: '*',
    f: 'geojson',
    outSR: outSR,
  });
  return `${serviceUrl}/query?${params.toString()}`;
}

function loadDataset(datasetId) {
  const ds = config.datasets.find((d) => d.id === datasetId);
  if (!ds) return;

  if (activeLayer) {
    map.removeLayer(activeLayer);
  }

  const source = new ol.source.Vector({
    url: buildQueryUrl(ds.serviceUrl),
    format: new ol.format.GeoJSON({
      // The service was asked to return geometry already in the project
      // CRS via outSR, so no client-side reprojection is needed here.
      dataProjection: projectProjection,
      featureProjection: projectProjection,
    }),
  });

  activeLayer = new ol.layer.Vector({ source });
  map.addLayer(activeLayer);

  source.once('featuresloadend', () => {
    const extent = source.getExtent();
    if (extent && isFinite(extent[0])) {
      view.fit(extent, { padding: [40, 40, 40, 40], maxZoom: 14 });
    }
  });
}

// --- 4. Wire up the dataset selector -------------------------------
const select = document.getElementById('dataset-select');

const params = new URLSearchParams(window.location.search);
const requested = params.get('dataset');
if (requested && config.datasets.some((d) => d.id === requested)) {
  select.value = requested;
}

select.addEventListener('change', (e) => loadDataset(e.target.value));
loadDataset(select.value);
