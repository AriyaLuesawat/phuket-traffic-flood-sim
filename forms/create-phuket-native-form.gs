/**
 * สร้างแบบสอบถามผู้ใช้ระบบ Phuket Native (หน้าแสดงผลจำลองจราจร ฝน และน้ำท่วมภูเก็ต แบบ 2D/3D)
 * เป็น Google Form พร้อม Google Sheet สำหรับเก็บคำตอบ ใช้หลังผู้ตอบได้ทดลองใช้หน้าแสดงผล (ขั้นที่ 9)
 *
 * ข้อคำถามมาจากแหล่งที่ตีพิมพ์แล้ว ปรับถ้อยคำให้เข้ากับระบบ (ต้นฉบับภาษาอังกฤษอยู่ในรายการด้านล่าง)
 * แสดงต่อผู้ตอบเป็นภาษาไทยอย่างเดียว:
 *   - ตอนที่ 1: ข้อมูลทั่วไป อายุและประสบการณ์เป็นตัวแปรกำกับของ UTAUT
 *       Venkatesh, Morris, Davis & Davis (2003), MIS Quarterly 27(3), 425–478.
 *   - ตอนที่ 2: System Usability Scale, Brooke (1996) ครบ 10 ข้อ (ตัดไม่ได้ เพราะคะแนนต้องใช้ทุกข้อ)
 *   - ตอนที่ 3: End-User Computing Satisfaction, Doll & Torkzadeh (1988), MIS Quarterly 12(2), 259–274
 *       ใช้ 2 ด้าน 5 ข้อ คือเนื้อหา (C1, C3, C4) และรูปแบบ (F1, F2) ตัดด้านความถูกต้องเพราะผู้ใช้
 *       ตัดสินความถูกต้องของผลจำลองเองไม่ได้ ตัดด้านความทันเวลาเพราะเป็นผลจำลอง ไม่ใช่ข้อมูลสด
 *       และตัดด้านความง่ายเพราะซ้ำกับ SUS
 *   - ตอนที่ 4: Perceived Usefulness, Davis (1989), MIS Quarterly 13(3), 319–340 – ใช้ 4 จาก 6 ข้อ
 *   - ตอนที่ 5: Continuance Intention, Bhattacherjee (2001), MIS Quarterly 25(3), 351–370 – ใช้ 2 จาก 3 ข้อ
 *   - ตอนที่ 6: ความรู้ในพื้นที่ – ผู้วิจัยพัฒนาขึ้นเอง ไม่บังคับตอบ ใช้ตรวจสอบผลจำลองเชิงคุณภาพ
 *       (ขั้นที่ 10) ไม่ใช่มาตรวัดที่ผ่านการตรวจความเที่ยง ต้องระบุเช่นนี้ใน manuscript
 *   ตอนที่ 2–5 ใช้มาตรวัดเห็นด้วย 5 ระดับเหมือนกัน
 *
 * วิธีใช้:
 *   1. ไปที่ https://script.google.com แล้วสร้างโปรเจกต์ใหม่
 *   2. วางไฟล์นี้ทั้งหมดลงใน Code.gs แล้วบันทึก
 *   3. เลือกฟังก์ชัน createPhuketNativeForm แล้วกด Run (ครั้งแรกต้องกดอนุญาตสิทธิ์)
 *   4. เปิด Execution log เพื่อดูลิงก์แก้ไขฟอร์ม ลิงก์ส่งให้ผู้ตอบ และลิงก์ชีตคำตอบ
 *   5. เมื่อได้คำตอบแล้ว รัน addScores เพื่อคำนวณคะแนน
 */

const AGREE = ['ไม่เห็นด้วยอย่างยิ่ง', 'เห็นด้วยอย่างยิ่ง'];
const SCALE_HELP = 'เลือก 1–5: 1 = ไม่เห็นด้วยอย่างยิ่ง · 2 = ไม่เห็นด้วย · 3 = เฉย ๆ · 4 = เห็นด้วย · 5 = เห็นด้วยอย่างยิ่ง';

// [รหัส, ข้อความไทยที่แสดงในฟอร์ม, ต้นฉบับภาษาอังกฤษ]
const SUS_ITEMS = [
  ['SUS1', 'ฉันอยากใช้ Phuket Native เป็นประจำ', 'I think that I would like to use this system frequently.'],
  ['SUS2', 'Phuket Native ซับซ้อนเกินความจำเป็น', 'I found the system unnecessarily complex.'],
  ['SUS3', 'Phuket Native ใช้งานง่าย', 'I thought the system was easy to use.'],
  ['SUS4', 'ฉันต้องมีคนที่เก่งคอมพิวเตอร์คอยช่วย จึงจะใช้ Phuket Native ได้', 'I think that I would need the support of a technical person to be able to use this system.'],
  ['SUS5', 'เมนูและฟังก์ชันต่าง ๆ ใน Phuket Native ทำงานต่อเนื่องกันดี', 'I found the various functions in this system were well integrated.'],
  ['SUS6', 'หน้าจอแต่ละส่วนของ Phuket Native ไม่ไปในทางเดียวกัน ทำให้สับสน', 'I thought there was too much inconsistency in this system.'],
  ['SUS7', 'คนส่วนใหญ่น่าจะเรียนรู้วิธีใช้ Phuket Native ได้เร็ว', 'I would imagine that most people would learn to use this system very quickly.'],
  ['SUS8', 'Phuket Native ใช้งานยุ่งยาก', 'I found the system very cumbersome to use.'],
  ['SUS9', 'ฉันมั่นใจตอนใช้ Phuket Native', 'I felt very confident using the system.'],
  ['SUS10', 'ฉันต้องเรียนรู้หลายอย่างก่อนจะเริ่มใช้ Phuket Native ได้', 'I needed to learn a lot of things before I could get going with this system.'],
];

const EUCS_ITEMS = [
  ['C1', 'Phuket Native แสดงข้อมูลที่ฉันต้องการรู้ เช่น ถนนเส้นไหนรถติด จุดไหนน้ำท่วม', 'Does the system provide the precise information you need?'],
  ['C3', 'แผนที่และกราฟใน Phuket Native ตอบสิ่งที่ฉันอยากรู้ได้ตรงประเด็น', 'Does the system provide reports that seem to be just about exactly what you need?'],
  ['C4', 'ข้อมูลใน Phuket Native ครบพอ ไม่ต้องไปหาที่อื่นเพิ่ม', 'Does the system provide sufficient information?'],
  ['F1', 'Phuket Native จัดวางแผนที่และข้อมูลให้ดูและใช้งานได้สะดวก', 'Do you think the output is presented in a useful format?'],
  ['F2', 'สีและสัญลักษณ์บนแผนที่เข้าใจง่าย ไม่กำกวม', 'Is the information clear?'],
];

const PU_ITEMS = [
  ['PU1', 'Phuket Native ช่วยให้ฉันวางแผนการเดินทางช่วงฝนตกได้เร็วขึ้น', 'Using the system in my job would enable me to accomplish tasks more quickly.'],
  ['PU2', 'Phuket Native ช่วยให้ฉันวางแผนการเดินทางช่วงฝนตกได้ดีขึ้น', 'Using the system would improve my job performance.'],
  ['PU5', 'Phuket Native ทำให้การวางแผนเดินทางช่วงฝนตกหรือน้ำท่วมง่ายขึ้น', 'Using the system would make it easier to do my job.'],
  ['PU6', 'โดยรวมแล้ว Phuket Native มีประโยชน์กับฉัน', 'I would find the system useful in my job.'],
];

const CI_ITEMS = [
  ['CI1', 'ถ้ามีให้ใช้จริง ฉันจะใช้ Phuket Native ต่อไป', 'I intend to continue using the system rather than discontinue its use.'],
  ['CI2', 'ฉันอยากใช้ Phuket Native มากกว่าวิธีเดิมที่เคยใช้ (เช่น ดูข่าว ถามในกลุ่มแชต ดูแอปแผนที่นำทาง)', 'My intentions are to continue using the system than use any alternative means.'],
];

const EUCS_DIMENSIONS = { 'เนื้อหา': 'C', 'รูปแบบ': 'F' };

// หัวข้อคำถามในฟอร์ม (และหัวคอลัมน์ในชีตคำตอบ) เป็นเลขข้อตามลำดับในแต่ละตอน
const titles_ = (items) => items.map(([, thai], i) => `${i + 1}. ${thai}`);

function createPhuketNativeForm() {
  const form = FormApp.create('แบบสอบถามความคิดเห็นต่อระบบ Phuket Native');
  form
    .setDescription(
      'แบบสอบถามนี้เป็นส่วนหนึ่งของงานวิจัย ขอความคิดเห็นของท่านหลังทดลองใช้ Phuket Native ' +
      'แผนที่จำลองการจราจรในภูเก็ตช่วงเวลาต่าง ๆ และผลของฝนตกจนถึงน้ำท่วม แบบ 2 มิติและ 3 มิติ\n\n' +
      '• ใช้เวลาประมาณ 5–7 นาที\n' +
      '• ไม่เก็บชื่อ อีเมล หรือข้อมูลที่ระบุตัวท่านได้\n' +
      '• ไม่มีคำตอบถูกหรือผิด ตอบตามที่รู้สึกจริง และหยุดตอบได้ทุกเมื่อ'
    )
    .setCollectEmail(false)
    .setLimitOneResponsePerUser(false)
    .setProgressBar(true)
    .setShowLinkToRespondAgain(false)
    .setConfirmationMessage('ขอบคุณที่ร่วมตอบแบบสอบถาม');

  // การยินยอม – ข้อกำหนดด้านจริยธรรม ไม่ใช่ข้อวัดผล หากไม่ยินยอมจะจบแบบสอบถามทันที
  const consent = form.addMultipleChoiceItem()
    .setTitle('ท่านยินยอมเข้าร่วมการวิจัยนี้หรือไม่')
    .setHelpText('คำตอบของท่านจะใช้เพื่องานวิจัยนี้เท่านั้น และไม่ระบุตัวตน')
    .setRequired(true);

  // ตอนที่ 1 – ข้อมูลทั่วไป
  const profilePage = form.addPageBreakItem().setTitle('ตอนที่ 1 ข้อมูลทั่วไป');
  form.addMultipleChoiceItem()
    .setTitle('1. ท่านเกี่ยวข้องกับภูเก็ตในฐานะใด')
    .setChoiceValues(['อาศัยหรือทำงานในภูเก็ต', 'นักท่องเที่ยว / มาเยือนชั่วคราว', 'นักศึกษา', 'เจ้าหน้าที่หน่วยงานรัฐหรือท้องถิ่น'])
    .showOtherOption(true)
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('2. อายุ')
    .setChoiceValues(['18–24 ปี', '25–34 ปี', '35–44 ปี', '45–54 ปี', '55 ปีขึ้นไป'])
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('3. ท่านเดินทางในภูเก็ตด้วยวิธีใดบ่อยที่สุด')
    .setChoiceValues(['รถจักรยานยนต์', 'รถยนต์ส่วนตัว', 'รถโดยสารสาธารณะ / รถรับจ้าง', 'ไม่ได้เดินทางในภูเก็ตเป็นประจำ'])
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('4. ในช่วง 1 ปีที่ผ่านมา ท่านเคยเจอน้ำท่วมถนนในภูเก็ตจนเดินทางลำบากกี่ครั้ง')
    .setChoiceValues(['ไม่เคย', '1–2 ครั้ง', '3–5 ครั้ง', 'มากกว่า 5 ครั้ง'])
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('5. ท่านใช้แอปแผนที่หรือแอปนำทางบ่อยแค่ไหน')
    .setChoiceValues(['ไม่เคย', 'น้อยกว่าเดือนละครั้ง', 'เดือนละ 1–4 ครั้ง', 'หลายครั้งต่อสัปดาห์'])
    .setRequired(true);

  addPart_(form, 'ตอนที่ 2 การใช้งานระบบ', 'บางข้อเป็นด้านบวก บางข้อเป็นด้านลบ โปรดอ่านให้ครบก่อนตอบ\n' + SCALE_HELP, SUS_ITEMS);
  addPart_(form, 'ตอนที่ 3 ข้อมูลและการแสดงผล', SCALE_HELP, EUCS_ITEMS);
  addPart_(form, 'ตอนที่ 4 ประโยชน์ของระบบ', SCALE_HELP, PU_ITEMS);
  addPart_(form, 'ตอนที่ 5 การใช้ระบบต่อ', SCALE_HELP, CI_ITEMS);

  // ตอนที่ 6 – ผู้วิจัยพัฒนาขึ้นเอง ใช้ตรวจผลจำลองกับประสบการณ์จริงของผู้ตอบ
  form.addPageBreakItem()
    .setTitle('ตอนที่ 6 ความรู้ในพื้นที่ (ไม่บังคับ)')
    .setHelpText('ตอบเฉพาะถ้าท่านคุ้นเคยกับถนนในภูเก็ต');
  form.addMultipleChoiceItem()
    .setTitle('1. จุดน้ำท่วมที่ระบบแสดง ตรงกับที่ท่านเคยเห็นจริงหรือไม่')
    .setChoiceValues(['ตรงเกือบทั้งหมด', 'ตรงบางส่วน', 'ไม่ค่อยตรง', 'ไม่ทราบ']);
  form.addParagraphTextItem()
    .setTitle('2. จุดที่ท่านเคยเจอน้ำท่วมขังจนขับรถผ่านลำบาก (ชื่อถนน แยก หรือสถานที่ใกล้เคียง)');

  form.addPageBreakItem().setTitle('ตอนที่ 7 ข้อเสนอแนะ (ไม่บังคับ)');
  form.addParagraphTextItem().setTitle('1. สิ่งที่ท่านชอบในระบบ');
  form.addParagraphTextItem().setTitle('2. สิ่งที่ควรปรับปรุง');

  consent.setChoices([
    consent.createChoice('ยินยอม', profilePage),
    consent.createChoice('ไม่ยินยอม (จบแบบสอบถาม)', FormApp.PageNavigationType.SUBMIT),
  ]);

  const sheet = SpreadsheetApp.create('Phuket Native – คำตอบแบบสอบถาม');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());
  PropertiesService.getScriptProperties().setProperty('SHEET_ID', sheet.getId());

  Logger.log('ลิงก์แก้ไขฟอร์ม:        ' + form.getEditUrl());
  Logger.log('ลิงก์ส่งให้ผู้ตอบ:       ' + form.getPublishedUrl());
  Logger.log('ลิงก์ชีตคำตอบ:          ' + sheet.getUrl());
}

function addPart_(form, title, helpText, items) {
  form.addPageBreakItem().setTitle(title).setHelpText(helpText);
  titles_(items).forEach((title) => {
    form.addScaleItem()
      .setTitle(title)
      .setBounds(1, 5)
      .setLabels(AGREE[0], AGREE[1])
      .setRequired(true);
  });
}

/**
 * รันหลังได้คำตอบ เพิ่มคอลัมน์คะแนนในชีตคำตอบ:
 *   SUS score     – Brooke (1996): ข้อคี่ (คะแนน − 1), ข้อคู่ (5 − คะแนน), รวม × 2.5 (0–100)
 *   EUCS <ด้าน>   – ค่าเฉลี่ยรายด้าน 2 ด้าน และ EUCS รวม (1–5)
 *   PU mean       – ค่าเฉลี่ย 4 ข้อ (1–5)
 *   CI mean       – ค่าเฉลี่ย 2 ข้อ (1–5)
 */
function addScores() {
  const sheetId = PropertiesService.getScriptProperties().getProperty('SHEET_ID');
  if (!sheetId) throw new Error('ต้องรัน createPhuketNativeForm ในโปรเจกต์นี้ก่อน');
  const sheet = SpreadsheetApp.openById(sheetId).getSheets()[0];
  const data = sheet.getDataRange().getValues();
  const header = data[0];
  const cols = (items) => {
    const found = titles_(items).map((title) => header.indexOf(title));
    if (found.some((c) => c < 0)) throw new Error('ไม่พบคอลัมน์ของบางข้อในชีตคำตอบ');
    return found;
  };
  const susCols = cols(SUS_ITEMS);
  const eucsCols = cols(EUCS_ITEMS);
  const puCols = cols(PU_ITEMS);
  const ciCols = cols(CI_ITEMS);
  const dimensions = Object.entries(EUCS_DIMENSIONS);

  const names = ['SUS score', ...dimensions.map(([name]) => 'EUCS ' + name), 'EUCS รวม', 'PU mean', 'CI mean'];
  const outputs = names.map((name) => {
    let c = header.indexOf(name);
    if (c < 0) {
      c = header.length;
      sheet.getRange(1, c + 1).setValue(name);
      header.push(name);
    }
    return c;
  });

  const mean = (values) => values.reduce((a, b) => a + b, 0) / values.length;
  for (let r = 1; r < data.length; r++) {
    const row = data[r];
    const sus = susCols.map((c) => Number(row[c]));
    if (sus.some((a) => !a)) continue; // ไม่ยินยอมหรือตอบไม่ครบ
    const susScore = sus.reduce((acc, a, i) => acc + (i % 2 === 0 ? a - 1 : 5 - a), 0) * 2.5;
    const eucs = eucsCols.map((c) => Number(row[c]));
    const dimensionMeans = dimensions.map(([, prefix]) =>
      mean(eucs.filter((_, i) => EUCS_ITEMS[i][0].startsWith(prefix))));
    const pu = mean(puCols.map((c) => Number(row[c])));
    const ci = mean(ciCols.map((c) => Number(row[c])));
    const values = [susScore, ...dimensionMeans, mean(eucs), pu, ci];
    values.forEach((value, i) => sheet.getRange(r + 1, outputs[i] + 1).setValue(value));
  }
}
