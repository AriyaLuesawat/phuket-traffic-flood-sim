# รายการอ้างอิง Phuket Native

รูปแบบ APA 7 ปรับปรุง 3 พ.ย. 2569
**ตรวจทุกรายการใน manuscript 18 พ.ย. 2569:** เปิดลิงก์จริง เทียบชื่อเรื่อง ผู้แต่ง ปี กับต้นทาง (Crossref/DataCite/arXiv/หน้าเว็บ) ลิงก์เปิดได้ทุกรายการ ยกเว้น DOI ของ Wiley 2 รายการ (Hersbach et al., 2020; Soille, 2004) ที่บล็อกโปรแกรมอัตโนมัติ (403) แต่ DOI ลงทะเบียนจริงและข้อมูลตรง เปิดในเบราว์เซอร์ได้


สถานะ:
- ✅ ตรวจบรรณานุกรมกับต้นฉบับ, Crossref หรือ DataCite แล้ว
- 📄 มีไฟล์ใน `docs/papers/`
- 🔍 ยังตรวจไม่ครบ ต้องตรวจก่อนส่ง paper (หมายเหตุอยู่ท้ายรายการ)

แต่ละรายการระบุว่าใช้ในขั้นไหน

## 1. ข้อมูล

- ✅ กรมทางหลวงชนบท. (2569). *สถิติปริมาณจราจร ปี 2569* [ชุดข้อมูล]. ศูนย์กลางข้อมูลเปิดกระทรวงคมนาคม. https://datagov.mot.go.th/dataset/aadt1 — ขั้น 4
- ✅ กรมทางหลวง. (2563). *ปริมาณจราจรบนทางหลวง ปี 2562* [ชุดข้อมูล]. ศูนย์กลางข้อมูลเปิดภาครัฐ. https://data.go.th/dataset/highwaystraffic2562 — ขั้น 4 · AADT (คัน/วัน) รายจุดสำรวจ ไฟล์ `doh-aadt-2562.csv` เผยแพร่ 24 มิ.ย. 2563 **แก้ 18 พ.ย. 2569:** เดิมอ้างชุด "ปริมาณการเดินทางบนทางหลวง" (datagov.mot.go.th/dataset/aadt, หน่วยคัน-กม.) ซึ่งไม่ใช่ไฟล์ที่ใช้คำนวณ (`doh-vk-*.csv` ใช้ดูภาพรวมเท่านั้น)
- ✅ สำนักงานสถิติแห่งชาติ. (2567). *Statistical yearbook Thailand 2024*. https://nso.go.th/public/e-book/Statistical-Yearbook/SYB-2024/619 — ขั้น 5 (เกณฑ์ปริมาณฝน 24 ชม. ของกรมอุตุนิยมวิทยา)
- ✅ Hersbach, H., Bell, B., Berrisford, P., Hirahara, S., Horányi, A., Muñoz-Sabater, J., Nicolas, J., Peubey, C., Radu, R., Schepers, D., Simmons, A., Soci, C., Abdalla, S., Abellan, X., Balsamo, G., Bechtold, P., Biavati, G., Bidlot, J., Bonavita, M., … Thépaut, J.-N. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society, 146*(730), 1999–2049. https://doi.org/10.1002/qj.3803 — ขั้น 5–6
- ✅ Zippenfenig, P. (2023). *Open-Meteo.com weather API* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.7970649 — ช่องทางดึง ERA5 · ขั้น 2 (รูปแบบอ้างอิงที่ Open-Meteo แนะนำ)
- ✅ European Space Agency, & Airbus. (2022). *Copernicus DEM* [ชุดข้อมูล]. https://doi.org/10.5270/ESA-c5d3d65 — GLO-30 ผ่าน AWS Open Data · ขั้น 6 (ผู้แต่งตาม DataCite)
- ✅📄 Zanaga, D., Van De Kerchove, R., Daems, D., De Keersmaecker, W., Brockmann, C., Kirches, G., Wevers, J., Cartus, O., Santoro, M., Fritz, S., Lesiv, M., Herold, M., Tsendbazar, N.-E., Xu, P., Ramoino, F., & Arino, O. (2022). *ESA WorldCover 10 m 2021 v200* [ชุดข้อมูล]. Zenodo. https://doi.org/10.5281/zenodo.7254221 — ขั้น 6
- ✅ OpenStreetMap contributors. (2026). *OpenStreetMap* [ชุดข้อมูล, ไฟล์ Geofabrik ณ 1 พ.ย. 2569]. https://www.openstreetmap.org — ขั้น 3 และ 6 (ODbL)
- ✅📄 Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., & Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed. *Environmental Research Letters, 17*(2), 024016. https://doi.org/10.1088/1748-9326/ac4d4f — FABDEM V1-2 ข้อมูลความสูงหลักของขั้น 6 (โหลดผ่านแพ็กเกจ `fabdem` 3 พ.ย. 2569)

## 2. เครื่องมือ

- ✅ Álvarez López, P., Behrisch, M., Bieker-Walz, L., Erdmann, J., Flötteröd, Y.-P., Hilbrich, R., Lücken, L., Rummel, J., Wagner, P., & Wießner, E. (2018). Microscopic traffic simulation using SUMO. In *2018 21st International Conference on Intelligent Transportation Systems (ITSC)* (pp. 2575–2582). IEEE. https://doi.org/10.1109/ITSC.2018.8569938 — ขั้น 3–5
- ✅📄 Eissfeldt, N. G. (2004). *Vehicle-based modelling of traffic: Theory and application to environmental impact modelling* [Doctoral dissertation, Universität zu Köln]. https://kups.ub.uni-koeln.de/1274/ — แบบจำลอง mesoscopic ของ SUMO · ขั้น 4
- ✅ Eclipse SUMO. (n.d.). *Simulation/Meso* [เอกสารประกอบ]. https://sumo.dlr.de/docs/Simulation/Meso.html — ขั้น 4
- ✅ Eclipse SUMO. (n.d.). *routeSampler.py* [เอกสารประกอบ]. https://sumo.dlr.de/docs/Tools/Turns.html#routesamplerpy — ขั้น 4
- ✅ The jamovi project. (2025). *jamovi* (Version 2.7) [Computer software]. https://www.jamovi.org — วิเคราะห์แบบสอบถาม · ติดตั้งในเครื่องคือ 2.7.41 · ปีให้ตรวจจากเมนู "Cite" ของ jamovi

## 3. ปรับเทียบแบบจำลองจราจร (ขั้น 4)

- ✅📄 Department for Transport. (2026). *TAG unit M3.1: Highway assignment modelling* (May 2026 version). GOV.UK. https://www.gov.uk/government/publications/tag-unit-m3-1-highway-assignment-modelling — ตาราง 2 (ฉบับ พ.ค. 2026 ตรวจ 18 พ.ย. 2569 แล้ว เกณฑ์ GEH < 5 มากกว่า 85% ของจุดนับ เหมือนฉบับ 2024)
- ✅📄 Ni, Y.-C., Akopian, A., Kouvelas, A., & Makridis, M. A. (2026). *Revisiting mesoscopic traffic flow simulation in SUMO: Limitations, analysis, and an alternative* [Preprint]. arXiv. https://arxiv.org/abs/2606.09282 — ข้อจำกัดของ meso · ยังไม่ได้อ่านฉบับเต็ม · ตรวจ 18 พ.ย. 2569: บทคัดย่อ (v2, 25 ก.ค. 2026) ระบุว่าแบบ Eissfeldt ใน SUMO ไม่สอดคล้องกับ LWR และประเมินรถติดต่ำกว่าจริง ตรงกับที่อ้าง

## 4. ผลของฝนต่อการจราจร (ขั้น 5)

- ✅ Transportation Research Board. (2010). *Highway capacity manual 2010*. Exhibit 10-15 — ยังไม่ได้เปิดต้นฉบับ ใช้ค่าจาก FHWA (2013) ตาราง 33 ที่พิมพ์ซ้ำ ใน paper ควรอ้างว่า "TRB (2010) as cited in FHWA (2013)" · **18 พ.ย. 2569:** อ้างแบบทุติยภูมิตาม APA 7 คือในเนื้อหาเขียน "Transportation Research Board, 2010, อ้างใน FHWA, 2013" และใส่เฉพาะ FHWA (2013) ในรายการอ้างอิง
- ✅📄 Federal Highway Administration. (2013). *Guide for highway capacity and operations analysis of active transportation and demand management strategies* (FHWA-HOP-13-042), Appendix A. https://ops.fhwa.dot.gov/publications/fhwahop13042/appa.htm — ตาราง 33 (HCM 2010), ตาราง 34 (SHRP 2-L08), ตาราง 36 · สำเนาเว็บ `fhwa-hop-13-042-appa.html`
- ✅📄 Takano, T., Morita, H., Napaporn, P., Vichiensan, V., & Nakamura, S. (2023). Statistical analysis of rainfall impacts on urban traffic in Bangkok, Thailand. *Hydrological Research Letters, 17*(4), 85–91. https://doi.org/10.3178/hrl.17.85 — ค่าเทียบของไทย (ฝน 10 มม./ชม. ความเร็วลด ~10.3%)

## 5. แบบจำลองน้ำท่วม (ขั้น 6)

- ✅ Bates, P. D., Horritt, M. S., & Fewtrell, T. J. (2010). A simple inertial formulation of the shallow water equations for efficient two-dimensional flood inundation modelling. *Journal of Hydrology, 387*(1–2), 33–45. https://doi.org/10.1016/j.jhydrol.2010.03.027 — สมการการไหล
- ✅📄 United States Department of Agriculture, Soil Conservation Service. (1986). *Urban hydrology for small watersheds* (Technical Release 55, 2nd ed.). U.S. Government Publishing Office. https://www.govinfo.gov/content/pkg/CZIC-gb980-u73-1986/pdf/CZIC-gb980-u73-1986.pdf — ตาราง 2-2a, 2-2b, 2-2c (curve number) · ปี 1986 หน่วยงานยังชื่อ Soil Conservation Service
- ✅ Barnes, R., Lehman, C., & Mulla, D. (2014). Priority-flood: An optimal depression-filling and watershed-labeling algorithm for digital elevation models. *Computers & Geosciences, 62*, 117–127. https://doi.org/10.1016/j.cageo.2013.04.024 — การเติมแอ่งใน DEM
- ✅ Soille, P. (2004). Optimal removal of spurious pits in grid digital elevation models. *Water Resources Research, 40*(12), W12509. https://doi.org/10.1029/2004WR003060 — เติมแอ่งด้วย morphological reconstruction
- ✅ Lindsay, J. B. (2016). The practice of DEM stream burning revisited. *Earth Surface Processes and Landforms, 41*(5), 658–668. https://doi.org/10.1002/esp.3888 — ฝังร่องลำน้ำ OSM ลงใน DEM (แก้ปัญหาถนนท่วมเกินจริงในขั้น 7)
- ✅ U.S. Army Corps of Engineers, Hydrologic Engineering Center. (n.d.). *HEC-RAS 2D user's manual (Version 6.6): Creating land cover, Manning's n values, and % impervious layers*. Retrieved November 18, 2026, from https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.6/developing-a-terrain-model-and-geospatial-layers/creating-land-cover-mannings-n-values-and-impervious-layers — ตารางค่า n ของฉบับ 6.6 ตรงกับหน้า latest ที่ใช้ตอนทำงาน

## 6. น้ำท่วมกับการจราจร (ขั้น 7)

- ✅📄 Pregnolato, M., Ford, A., Wilkinson, S. M., & Dawson, R. J. (2017). The impact of flooding on road transport: A depth-disruption function. *Transportation Research Part D: Transport and Environment, 55*, 67–81. https://doi.org/10.1016/j.trd.2017.06.020

## 7. แบบสอบถาม Phuket Native (`forms/create-phuket-native-form.gs`)

- ✅ Brooke, J. (1996). SUS: A "quick and dirty" usability scale. In P. W. Jordan, B. Thomas, B. A. Weerdmeester, & I. L. McClelland (Eds.), *Usability evaluation in industry* (pp. 189–194). Taylor & Francis. — ตอนที่ 2 (SUS 10 ข้อ) และวิธีคิดคะแนน 0–100
- ✅ Doll, W. J., & Torkzadeh, G. (1988). The measurement of end-user computing satisfaction. *MIS Quarterly, 12*(2), 259–274. https://doi.org/10.2307/248851 — ตอนที่ 3 (EUCS ด้านเนื้อหาและรูปแบบ 5 ข้อ)
- ✅ Davis, F. D. (1989). Perceived usefulness, perceived ease of use, and user acceptance of information technology. *MIS Quarterly, 13*(3), 319–340. https://doi.org/10.2307/249008 — ตอนที่ 4 (PU 4 ข้อ)
- ✅ Bhattacherjee, A. (2001). Understanding information systems continuance: An expectation-confirmation model. *MIS Quarterly, 25*(3), 351–370. https://doi.org/10.2307/3250921 — ตอนที่ 5 (CI 2 ข้อ)
- ✅ Venkatesh, V., Morris, M. G., Davis, G. B., & Davis, F. D. (2003). User acceptance of information technology: Toward a unified view. *MIS Quarterly, 27*(3), 425–478. https://doi.org/10.2307/30036540 — ตอนที่ 1 (อายุและประสบการณ์เป็นตัวแปรกำกับ)
- ตอนที่ 6 (ความรู้ในพื้นที่) ผู้วิจัยพัฒนาเอง ไม่มีอ้างอิง ต้องระบุใน paper

## 8. ความตรงและความเชื่อมั่นของแบบสอบถาม (แล็บ jamovi)

- 🔍 Rovinelli, R. J., & Hambleton, R. K. (1977). On the use of content specialists in the assessment of criterion-referenced test item validity. *Dutch Journal of Educational Research, 2*, 49–60. — ดัชนี IOC · ยืนยันได้จากรายการอ้างอิงของบทความอื่นเท่านั้น บางแหล่งระบุปี 1976 (ฉบับเสนอในที่ประชุม)
- ✅ Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests. *Psychometrika, 16*(3), 297–334. https://doi.org/10.1007/BF02310555 — Cronbach's α
- 🔍 George, D., & Mallery, P. (2003). *SPSS for Windows step by step: A simple guide and reference, 11.0 update* (4th ed.). Allyn & Bacon. — เกณฑ์แปลผล α (> .9 ดีมาก … < .5 ใช้ไม่ได้) · ยืนยันได้จากแหล่งที่อ้างต่อ เช่น Indiana University Knowledge Base ยังไม่ได้เห็นหน้าในหนังสือ

## 9. จุดน้ำท่วมที่ใช้ตรวจผล (ขั้น 6 และ 10)

- ✅ กรุงเทพธุรกิจ. (2569, 29 ตุลาคม). *น้ำท่วมภูเก็ตล่าสุด ฝนตกหนัก 70% 'ถนนโคกโตนด-หน้าวัดใต้' ผ่านไม่ได้*. https://www.bangkokbiznews.com/news/1258382 — F01–F02 (ข่าว 1258282 ลงวันที่ 28 ต.ค. เป็นข่าวเตือนน้ำทะเลหนุน ไม่ได้รายงานจุดน้ำท่วม เอาออกแล้ว)
- ✅ ไทยโพสต์. (2569, 29 ตุลาคม). *ฝนถล่มภูเก็ต น้ำท่วมสูงหลายจุด เทศบาลประกาศเตือนภัย 'ธงแดง' ยกของขึ้นที่สูง*. https://www.thaipost.net/district-news/1097443/ — F03–F14
- ✅ สยามรัฐ. (2569, 29 ตุลาคม). *ภูเก็ตฝนถล่มต่อเนื่อง น้ำท่วมหลายจุด รถเล็กสัญจรลำบาก เทศบาลเตือนรหัสแดงริมคลองบางใหญ่*. https://siamrath.co.th/regional/332013 — F15, F17
- ✅ TNews. (2569, 29 ตุลาคม). *ฝนถล่ม ภูเก็ตเช้านี้น้ำท่วมหลายจุด กระทบการจราจรหลายเส้น*. https://www.tnews.co.th/social/social-news/662496 — F16
- ✅ Spacebar. (2569, 29 ตุลาคม). *ภูเก็ตวิกฤต! ฝนสะสมตกแช่นาน 2 วัน น้ำท่วมหลายจุด เทศบาลเตือน "ธงแดง" คลองหลักรับมือระดับน้ำเพิ่มสูงขึ้น*. https://spacebar.th/social/phuket-remains-in-a-critical-situation-with-accumulated-rainfall-causing-high-flood-levels-in-many-areas — F18 และเวลาที่น้ำลด (10.00 น.)
- ❌ Thai PBS (https://www.thaipbs.or.th/news/content/341541) — **เอาออก 18 พ.ย. 2569:** เป็นข่าว 30 มิ.ย. 2567 ไม่ใช่เหตุการณ์ 29 ต.ค. 2569 และไม่มีจุดน้ำท่วมใดในไฟล์ข้อมูลมาจากข่าวนี้

## 10. พบแล้ว แต่ยังไม่ได้ใช้

- 🔍 วิทยานิพนธ์จุฬาลงกรณ์มหาวิทยาลัย (2553). *ค่าการจราจรสำหรับการวางแผนและออกแบบทางหลวงแผ่นดินในประเทศไทย*. https://doi.org/10.58837/CHULA.THE.2010.1494 — ค่า K ใช้แทนสมมติฐานสัดส่วนรายชั่วโมงได้ ยังโหลดไม่ได้
- 🔍 Hranac, R., Sterzin, E., Krechmer, D., Rakha, H., & Farzaneh, M. (2006). *Empirical studies on traffic flow in inclement weather* (FHWA-HOP-07-073). Federal Highway Administration. https://ops.fhwa.dot.gov/publications/weatherempirical/
- 🔍 ACRS 2012 (ม.สงขลานครินทร์ วิทยาเขตภูเก็ต). ผลของความละเอียด DEM ต่อการหาโครงข่ายลำน้ำของภูเก็ต. https://acrs-aars.org/proceeding/ACRS2012/Proceeding%20ACRS%202012/Technical%20Sessions/C4%20GIS%20and%20Web%20(3)/C4-4.pdf
- ✅ American Meteorological Society. (n.d.). *Rain*. Glossary of Meteorology. https://glossary.ametsoc.org/wiki/Rain
