"""Build one annotation workbook per member (Pilot + own batch + Lists). Usage: python scripts/build_annotation_workbooks.py pool.json data/annotations"""
import json, sys, csv, yaml
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

pool = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
tax = yaml.safe_load(open(Path(__file__).parent.parent / "configs" / "taxonomy.yaml"))
LISTS = {
 "has_event": tax["has_event_values"],
 "category": [c["id"] for c in tax["categories"]],
 "autonomy_level": ["0","1","2","3","4","NA"],
 "interaction": tax["interaction"],
 "capability": tax["capability_tags"],
 "phase_hint": ["1","2","3","4","5","6","7"],
 "confidence": ["1","2","3"],
}
META = ["annotation_id","doc_id","publication_date","source","source_type","title","url","text_excerpt"]
FIELDS = ["has_event","event_date","category","trigger","organization","model_agent","capability","action",
          "autonomy_level","interaction","impact","phase_hint","confidence","notes"]
WIDTH = dict(annotation_id=10,doc_id=16,publication_date=12,source=14,source_type=12,title=40,url=24,text_excerpt=70,
             has_event=18,event_date=12,category=26,trigger=22,organization=16,model_agent=18,capability=18,action=28,
             autonomy_level=10,interaction=16,impact=28,phase_hint=9,confidence=10,notes=30)
HEAD = PatternFill("solid", fgColor="DDEBF7"); FILL = PatternFill("solid", fgColor="FFF2CC")

def sheet(wb, name, docs, prefix):
    ws = wb.create_sheet(name); ws.append(META + FIELDS)
    for i, d in enumerate(docs, 1):
        ws.append([f"{prefix}{i:02d}" if prefix=="P" else f"{prefix}-{i:03d}", d["doc_id"], d["publication_date"], d["source"],
                   d["source_type"], d["title"], d["url"], d["text_excerpt"]] + [""]*len(FIELDS))
    cols = META + FIELDS
    for j, c in enumerate(cols, 1):
        L = ws.cell(1, j).column_letter; ws.column_dimensions[L].width = WIDTH[c]
        ws.cell(1, j).font = Font(bold=True); ws.cell(1, j).fill = HEAD if c in META else FILL
    for row in ws.iter_rows(min_row=2):
        for cell in row: cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "G2"
    n = len(docs) + 1
    for field, key in [("has_event","has_event"),("category","category"),("capability","capability"),
                       ("autonomy_level","autonomy_level"),("interaction","interaction"),("phase_hint","phase_hint"),("confidence","confidence")]:
        col = ws.cell(1, cols.index(field)+1).column_letter
        dv = DataValidation(type="list", formula1='"' + ",".join(LISTS[key]) + '"', allow_blank=True)
        ws.add_data_validation(dv); dv.add(f"{col}2:{col}{n}")
    return ws

for who in ["VV","SH","TS","HA"]:
    wb = Workbook(); r = wb.active; r.title = "README"
    for line in [f"Annotation workbook for {who}  (taxonomy v0 - DRAFT until the agreement meeting)",
        "1. Read docs/annotation_guidelines.md first.",
        "2. Do sheet 'Pilot' ALONE (15 docs, same for all four members). Do not discuss before the agreement meeting.",
        "3. After the meeting (taxonomy frozen as v1) do your own batch (75 docs).",
        "4. If has_event is not 'yes', leave the other yellow columns empty.",
        "5. event_date = date the event happened (YYYY-MM-DD, or YYYY-MM if only the month is known); publication_date is only a fallback.",
        "6. trigger = exact words from the text that signal the event. Do not paraphrase.",
        "7. Not sure? Pick the best label and set confidence=1; add a note. Never leave category blank for has_event=yes.",
        "8. Return the file to Harshita. Do not rename columns."]:
        r.append([line])
    r.column_dimensions["A"].width = 130
    sheet(wb, "Pilot", pool["pilot"], "P"); sheet(wb, f"Batch_{who}", pool[who], who)
    L = wb.create_sheet("Lists")
    for j,(k,v) in enumerate(LISTS.items(),1):
        L.cell(1,j,k).font = Font(bold=True)
        for i,x in enumerate(v,2): L.cell(i,j,x)
    wb.save(out / f"annotation_{who}.xlsx")

with open(out / "annotation_pool_v0.csv", "w", newline="") as f:   # master assignment (keeps auto hints; do NOT share with annotators)
    w = csv.writer(f); w.writerow(["batch","doc_id","publication_date","source","source_type","title","url","auto_hint"])
    for b, docs in pool.items():
        for d in docs: w.writerow([b,d["doc_id"],d["publication_date"],d["source"],d["source_type"],d["title"],d["url"],d["hint"]])
print("written", [p.name for p in out.iterdir()])
