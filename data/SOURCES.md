# แหล่งที่มาของข้อมูล (ขั้นที่ 2, ดาวน์โหลด 3 พ.ย. 2569)

ไฟล์ใน `data/raw/` และ `data/processed/` ไม่อยู่ใน git สร้างใหม่ได้ตามรายการนี้

| ไฟล์ | แหล่ง | รายละเอียด |
|---|---|---|
| `raw/osm/thailand-latest.osm.pbf` | Geofabrik https://download.geofabrik.de/asia/thailand-latest.osm.pbf | ข้อมูล OSM ณ 2026-11-01T21:21:36Z, © OpenStreetMap contributors (ODbL) |
| `processed/phuket.osm.pbf` | ตัดจากไฟล์ข้างบน `osmium extract -b 98.24,7.74,98.48,8.21` | 704,960 nodes / 120,362 ways; ถนน 26,987 เส้น (ถนนที่รถวิ่งได้ 13,964 เส้น รวม ~2,781 กม.), อาคาร 84,344 หลัง |
| `raw/dem/cop30_N07_00_E098_00.tif`, `cop30_N08_00_E098_00.tif` | Copernicus DEM GLO-30, s3://copernicus-dem-30m (AWS Open Data) | DSM 1 arc-second, © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA |
| `processed/phuket_cop30.tif` | รวมสองไทล์และตัดตามกรอบเดียวกัน | 1692 × 864 ช่อง, บนบก 648,596 ช่อง, สูงสุด 541.9 ม. (เป็นค่า DSM รวมต้นไม้) |
| `raw/rain/era5_phuket_town_2000_2026.json` | Open-Meteo Historical Weather API (ERA5) `latitude=7.884&longitude=98.392&hourly=precipitation&timezone=Asia/Bangkok` | ฝนรายชั่วโมง 2000-01-01 ถึง 2026-10-31 (235,224 ชั่วโมง) ช่องกริดที่ได้คือ 7.909N 98.370E |
| `raw/traffic/drr-aadt-2569.csv` | กรมทางหลวงชนบท https://datagov.mot.go.th/dataset/aadt1 | AADT ปี 2569 แยก 12 ประเภทรถ ภูเก็ต 20 สาย (รหัส ภก.) |
| `validation/flood-reports-2569-10-29.csv` | ข่าว กรุงเทพธุรกิจ และ ไทยโพสต์ 29 ต.ค. 2569 | 14 จุดที่ข่าวรายงานว่าน้ำท่วม; พิกัดจาก Nominatim (OSM) ได้ 9 จุด ต้องตรวจด้วยตา |
| `raw/traffic/doh-vk-2562.csv`, `doh-vk-2564.csv` | กรมทางหลวง https://datagov.mot.go.th/dataset/aadt (ผู้วิจัยดาวน์โหลดผ่านเบราว์เซอร์ 3 พ.ย. 2569) | ปริมาณการเดินทางรายตอนควบคุม แยก 10 ประเภทรถ + รถจักรยานยนต์; ภูเก็ต 19 ตอน; "รวม" ไม่นับรถจักรยานยนต์; หน่วยน่าจะเป็นคัน-กม./ปี (ไฟล์ไม่ระบุ ต้องยืนยัน); ปี 2564 รวมต่ำกว่าปี 2562 ราว 52% (โควิด) จึงใช้ปี 2562 เป็นค่าหลัก |
