// Copy to config.local.js (gitignored) to use a high-resolution satellite layer with your own key.
// Without config.local.js the "ดาวเทียม" mode uses EOX Sentinel-2 cloudless 2024 (10 m, no key, CC BY-NC-SA 4.0).
// Never commit a key: config.local.js is in .gitignore. A key in a public page is visible to every visitor, so use a
// key restricted to your domain (MapTiler/Esri dashboards allow this).
//
// year: the year of the imagery (shown in the note "ภาพดาวเทียมเป็นภาพพื้นหลังปี ..."); leave null if unknown.

// MapTiler satellite (https://www.maptiler.com/copyright/)
window.SAT_PROVIDER = {
  url: 'https://api.maptiler.com/tiles/satellite-v2/{z}/{x}/{y}.jpg?key=YOUR_KEY',
  attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank" rel="noopener">© MapTiler</a> ' +
               '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>',
  maxzoom: 19,
  year: null,
};

// Esri World Imagery (needs an ArcGIS location services key; check Esri's terms for your use)
// window.SAT_PROVIDER = {
//   url: 'https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token=YOUR_KEY',
//   attribution: 'Esri, Maxar, Earthstar Geographics, and the GIS User Community',
//   maxzoom: 19,
//   year: null,
// };
