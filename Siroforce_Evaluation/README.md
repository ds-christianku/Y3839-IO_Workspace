# Siroforce Evaluation – IO Sensor Ticket Analysis

Automated pipeline for classifying and analysing Siroforce tickets. Input is a set of CSV exports and an Excel lookup file; output is an interactive HTML report.

---

## Requirements

- Python 3.11 or newer
- Install dependencies:

```bash
pip install openpyxl xlrd
```

---

## Directory Structure

```
Siroforce_Evaluation/
├── input/                          # Input data (CSV + Excel)
│   ├── EXPORT_RH_1.csv … _10.csv
│   └── 20260731_IO_Imaging_SFTickets.xlsx
├── output/                         # Created automatically
│   ├── tickets_raw.json
│   └── tickets_classified.json
├── categories.json                 # Keyword configuration (editable)
├── pipeline_01_ingest.py           # Stage 1: CSV + Excel → JSON
├── pipeline_02_classify.py         # Stage 2: Classification
├── pipeline_03_render.py           # Stage 3: JSON → HTML
├── run_pipeline.py                 # Orchestrator
└── Ticket_Report_CSV.html          # Finished report (after pipeline run)
```

---

## Running the Pipeline

### Default (recommended)

```bash
cd Siroforce_Evaluation
python run_pipeline.py
```

Reads from `input/` automatically and writes the report to `Ticket_Report_CSV.html`.

### Options

| Option | Description |
|--------|-------------|
| `--output file.html` | Use a custom report file name |
| `--skip-ingest` | Skip Stage 1 – `output/tickets_raw.json` must already exist |
| `--skip-classify` | Skip Stage 1 + 2 – `output/tickets_classified.json` must already exist |
| `--input-dir path` | Use a different directory for CSV files |
| `--excel path` | Use a different Excel lookup file |
| `--sheet name` | Use a different sheet name in the Excel file (default: `IO 24Month`) |

### Examples

```bash
# Re-render only (classification already available)
python run_pipeline.py --skip-classify

# Custom report file name
python run_pipeline.py --output Report_August.html

# Different input data
python run_pipeline.py --input-dir ../other_data --excel ../other_data/lookup.xlsx --sheet "Sheet1"
```

### Running individual stages directly

```bash
python pipeline_01_ingest.py
python pipeline_02_classify.py
python pipeline_03_render.py
```

---

## Customising the Classification

The file `categories.json` controls all keyword lists without requiring any changes to Python code.  
Changes take effect automatically on the next pipeline run (from Stage 2 onwards).

---

## Using the HTML Report

Open the generated `Ticket_Report_CSV.html` in any browser — no server required, all filtering runs locally.

### Global Filters (top of the report)

| Filter | Description |
|--------|-------------|
| **Region Filter** | `ALL` / `US` / `EU` / `REST` – applies to all charts and KPI cards |
| **Time Period** | Last 1 / 2 / 3 / 6 / 12 months or overall date range |
| **Category Level 2** | Restrict to a single Excel category |
| **Firmware Version** | Restrict to a specific firmware version |
| **Record Type** | Multi-select: Complaint / Inquiry / Rest |

All filters apply simultaneously and update the entire report without reloading the page.

### Report Sections

**Description Analysis**  
Bar chart and pie chart of all primary ticket categories. The pie chart supports freely positionable text fields with connecting lines (*Add text field* button).

**Description Analysis – Detail**  
Drill-down view with subcategory filter and free-text search across ticket descriptions. Clicking a row in the top descriptions table shows all matching transactions. Clicking a transaction opens the Ticket Notes panel on the right.

The **Transaction Number** field below the table allows searching for a specific ticket ID directly — independent of the category or description filters. Typing any part of a transaction number immediately shows all matching rows across the full dataset.

**Spare Parts/RMA – Exchange Statistics**  
Breakdown of spare part and RMA tickets by type (Sensor, Remote, Sensor Cable, USB Cable).

**Ticket Clarity**  
Only visible when ticket notes are present. Shows the share of clearly documented tickets and the most common resolution paths.

**TOP 10 Major Issues**  
Automatic theme assignment for software, hardware, and imaging tickets based on notes content.

**Category Trend by Month**  
Line chart of the top 6 categories over the full date range (always unaffected by the time period filter to show the complete trend).
