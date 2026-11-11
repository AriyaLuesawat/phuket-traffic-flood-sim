# Runs the COM-101 lab analyses with jamovi's own engine (R package jmv bundled in jamovi.app),
# so the tables are identical to clicking them in jamovi. Also writes a ready .omv data file.
#
#   scripts/run_jamovi_r.sh scripts/jamovi_analysis.R data/synthetic/phuket-native-SYNTHETIC-n30.csv
args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]
suppressMessages({ library(jmv); library(jmvReadWrite) })

d <- read.csv(inp, fileEncoding = "UTF-8-BOM", stringsAsFactors = FALSE)
lv <- list(
  Role = c("นักศึกษา", "อาศัยหรือทำงานในภูเก็ต", "นักท่องเที่ยว / มาเยือนชั่วคราว", "เจ้าหน้าที่หน่วยงานรัฐหรือท้องถิ่น"),
  Age = c("18–24 ปี", "25–34 ปี", "35–44 ปี", "45–54 ปี", "55 ปีขึ้นไป"),
  TravelMode = c("รถจักรยานยนต์", "รถยนต์ส่วนตัว", "รถโดยสารสาธารณะ / รถรับจ้าง", "ไม่ได้เดินทางในภูเก็ตเป็นประจำ"),
  FloodEncounter = c("ไม่เคย", "1–2 ครั้ง", "3–5 ครั้ง", "มากกว่า 5 ครั้ง"),
  MapAppUse = c("ไม่เคย", "น้อยกว่าเดือนละครั้ง", "เดือนละ 1–4 ครั้ง", "หลายครั้งต่อสัปดาห์"),
  FloodMatch = c("ตรงเกือบทั้งหมด", "ตรงบางส่วน", "ไม่ค่อยตรง", "ไม่ทราบ"))
for (v in names(lv)) d[[v]] <- factor(d[[v]], levels = lv[[v]])
neg <- paste0("SUS", c(2, 4, 6, 8, 10))
pos <- paste0("SUS", c(1, 3, 5, 7, 9))
d$SUS_score <- (rowSums(d[pos] - 1) + rowSums(5 - d[neg])) * 2.5

out <- sub("\\.csv$", "-jamovi-output.txt", inp)
sink(out)
cat("jamovi engine: jmv", as.character(packageVersion("jmv")), "| file:", basename(inp), "| N =", nrow(d), "\n")
if (any(d$DataType == "SYNTHETIC")) cat("*** SYNTHETIC DATA - practice only, not real responses ***\n")

cat("\n==== Part I. Frequencies (Exploration > Descriptives > Frequency tables) ====\n")
print(do.call(descriptives, list(data = d, vars = names(lv), freq = TRUE, n = FALSE, missing = FALSE, mean = FALSE, median = FALSE,
                   sd = FALSE, min = FALSE, max = FALSE)))
cat("\n==== Chi-square goodness of fit, equal proportions (Frequencies > N Outcomes) ====\n")
# levels nobody chose are dropped, as when jamovi imports the CSV (Age 45–54 has no answers: df = 3)
# jmv functions read argument names literally, so variable names held in R variables go through do.call
for (v in names(lv)) print(do.call(propTestN, list(data = droplevels(d[v]), var = v)))

cat("\n==== Part II. Reliability + construct mean/SD (Factor > Reliability Analysis) ====\n")
rel <- list(SUS = paste0("SUS", 1:10), EUCS = c("C1", "C3", "C4", "F1", "F2"),
            PU = c("PU1", "PU2", "PU5", "PU6"), CI = c("CI1", "CI2"))
for (k in names(rel)) {
  cat("\n---", k, "---\n")
  opts <- list(data = d, vars = rel[[k]], alphaScale = TRUE, meanScale = TRUE, sdScale = TRUE,
               meanItems = TRUE, sdItems = TRUE, alphaItems = TRUE, itemRestCor = TRUE)
  if (k == "SUS") opts$revItems <- neg
  print(do.call(reliability, opts))
}
cat("\n==== Item mean/SD as answered (no reverse scoring) ====\n")
print(do.call(descriptives, list(data = d, vars = unname(unlist(rel)), n = FALSE, missing = FALSE, median = FALSE, min = FALSE, max = FALSE)))

cat("\n==== SUS score 0-100 (Exploration > Descriptives) ====\n")
print(descriptives(d, vars = "SUS_score", median = TRUE, range = TRUE, iqr = TRUE, pc = TRUE, pcValues = "25,50,75",
                   skew = TRUE, kurt = TRUE, sw = TRUE))
sink()

omv <- sub("\\.csv$", ".omv", inp)
write_omv(d, omv, frcWrt = TRUE)
cat("wrote", out, "and", omv, "\n")
