# Web viewer (step 9): MapLibre 3D, map and satellite looks

Same page as `web/app` (same menus, wording, colours, thresholds, URL `?p=&s=&f=&v=&tab=`, live rain), drawn with
MapLibre GL JS 4.7.1 instead of deck.gl, from smaller files.

```
.venv/bin/python scripts/pack_web_data.py     # reads web/app/data (export_web.py) + the FABDEM/sea rasters
cd web/app && python3 -m http.server 8773  # then open http://127.0.0.1:8773/?p=morning_peak&s=heavy_reports&f=14
```

`web/app/data/` is written by `scripts/export_web.py` (only the packer reads it); the page reads `data-c/`
(generated, gitignored).

URL: `?p=<period>&s=<scenario>&f=<frame>&v=2d|island&tab=live|sim&base=map|sat`. Debug only: `&perf` (bytes and time
to the first full draw), `&debug` (JS errors into the page), `&q=0|1|2` (fix the quality level), and
`&fakeloc=<lat>,<lon>` (a fake position, active only on localhost).

## Reset view

The compass button is icon-only; its needle turns with the map. First press: north up and the default tilt of the
current mode (3D 55°, 2D flat), zoom and centre kept. Press again while already north up: back to the starting view of
the last chosen place (ตัวเมือง / ทั้งเกาะ).

## Weather icon (live tab)

Our own small SVG icons (sun, moon, partly cloudy day/night, cloudy day/night (solid sun or cream moon with stars; partly cloudy = small white cloud, cloudy = big grey cloud), fog, drizzle, rain, heavy rain, thunderstorm),
each with a Thai label. **Rain comes from the ThaiWater stations** (raining or not, and how hard). **Open-Meteo**
(no key, CC BY 4.0, credited) only sets the sky: day or night, clear, cloud, fog, thunder. If the stations say it is
not raining, no rain icon is shown. Open-Meteo is asked once for the 10 place centres of `basemap.json` (your
position is never sent), and the page uses the place nearest to you, or ตัวเมืองภูเก็ต. It refreshes every 15 minutes
while the live tab is open and the browser tab is visible. If the request fails, the icon falls back to the
station rain plus day/night from the clock, with no temperature. Debug (localhost only):
`&fakewx=<weather_code>,<is_day>[,<latest measured rain mm>]`.

## Two looks: แผนที่ / ดาวเทียม

The choice is remembered in this browser (localStorage) and can be set with `&base=`.

- **แผนที่**: the dark look of prototype D: navy ground, light-grey solid buildings, faint grid (the 210 m ground
  lines of `terrain.json`), dark panels with cyan accents. Real FABDEM terrain with a dark hillshade.
- **ดาวเทียม**: EOX Sentinel-2 cloudless 2024 (10 m, no key) draped on the terrain. Licence CC BY-NC-SA 4.0
  (non-commercial); the attribution is shown in the credit line, and a note says that the image is from 2567 (2024),
  not from 29 Oct 2569. For sharper imagery, copy `config.example.js` to `config.local.js` (gitignored) and
  set `window.SAT_PROVIDER = { url, attribution, maxzoom, year }` with your own key (MapTiler or Esri). Never
  commit a key.

The road speed colours, thresholds and all wording are the same in both looks. Main roads have a dark casing.

## Location (📍)

A small card asks once "ตอนนี้คุณอยู่ในภูเก็ตไหม?". Only after "อยู่" (or the 📍 button) does the page ask the
browser for the position. The position stays in this browser: it is not sent to any server, not logged and not
put in the URL. With a position inside Phuket the page shows a blue dot with its accuracy circle and:

- **ฝนตอนนี้ตรงที่คุณอยู่**: the nearest ThaiWater station that reports hourly rain, its distance and rain level.
  The station list comes from the same public request as the live menu; it does not include your position.
- **ถนนใกล้คุณ**: the share of main roads within 2 km in each speed class in the scenario on the map, and the
  nearest road with "ควรเลี่ยง อาจมีน้ำท่วมขัง รอระบาย". In the simulation menu it says that this is the simulated
  scenario, not a forecast. In the live menu it says that the speeds are model estimates, and it says nothing
  about water, because the page does not predict floods from rain. The exception is when the 29 Oct 2569 example is
  shown, and then it is labelled as an example.

Geolocation needs a secure context: `localhost` works, but a phone needs **https** (for example GitHub Pages).

## Speed

- 2D loads no terrain or buildings. 3D fetches only the tiles in view. The flood water cells load only for
  "น้ำบนถนน (แบบจำลอง)", and the satellite tiles only in satellite mode.
- The data files are gzip, decoded in the browser:
  - roads 1.06 MB (vs 4.9 MB)
  - runs ~250 kB each (vs 2.4 MB)
  - buildings as vector tiles, ~1.1–1.4 MB for all of them, and only the visible tiles are fetched (vs 13.1 MB JSON)
- The vehicle dots and the 3D rain move on the GPU in one small WebGL2 layer. A 5-minute step only changes the
  roads whose colour class changed. While playing, the next step's dots are prepared when the browser is idle.
- While the user drags, zooms or rotates, the rain is hidden and the dots are frozen.
- Adaptive quality: if the frame rate stays below 28 fps for two 2-second windows while the map is busy, the page
  steps down:
  1. fog off, pixel ratio 1.5, half the rain drops
  2. hillshade off, pixel ratio 1, a quarter of the rain drops

  It never steps back up during the visit.
- The place names are HTML labels so the browser shapes Thai correctly (MapLibre's own text layer dropped or
  misplaced vowels and tone marks: "ตัวเมือง" became "ตามือง"). They move with one CSS transform each on the map's
  `move` event; there are only 10, so this is cheap.

## Known gaps

- Buildings are not drawn below zoom 12 (island view).
- The dots need WebGL2 (all current browsers); on WebGL1 they are not drawn.
- The water strips are UTM grid images placed in 4 strips, so a cell can be off by up to ~1.5 m.
- Not tested on a real phone (emulated 390×844 in headless Chrome only).
