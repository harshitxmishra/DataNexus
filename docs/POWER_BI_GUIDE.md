# DataNexus — Power BI & Business Intelligence Integration Guide

This guide describes how to connect **Power BI Desktop** or any standard BI tool (Tableau, Looker Studio, Metabase) to the curated analytical layer of DataNexus.

---

## 1. Connection Architecture

DataNexus isolates raw document storage from analytical reporting. Power BI connects directly to **PostgreSQL curated views** or consumes the one-click CSV analytical export from the Data Platform.

```
PostgreSQL (datanexus)
  ├── Dim Tables: dim_vendor, dim_date
  ├── Fact Tables: fact_invoice, fact_invoice_line, fact_pipeline_run
  └── Curated Views:
        ├── v_invoice_spend_by_vendor
        ├── v_overdue_invoices
        ├── v_daily_ingestion
        ├── v_processing_performance
        ├── v_data_quality_scorecard
        └── v_pipeline_freshness
```

---

## 2. Connecting Power BI Desktop to PostgreSQL

1. Open **Power BI Desktop**.
2. Select **Get Data** → **PostgreSQL Database** → Click **Connect**.
3. In the connection dialog, enter:
   - **Server**: `localhost:5432` (or your cloud PostgreSQL host)
   - **Database**: `datanexus`
   - **Data Connectivity mode**: **Import** (recommended for interactive reports) or **DirectQuery** (for live telemetry)
4. Under **Credentials**, select **Database** and enter your PostgreSQL username and password.
5. In the **Navigator** pane, select the following curated views from the `public` schema:
   - `v_invoice_spend_by_vendor`
   - `v_overdue_invoices`
   - `v_daily_ingestion`
   - `v_processing_performance`
   - `v_data_quality_scorecard`
   - `v_pipeline_freshness`
6. Click **Load**.

---

## 3. Alternative: Direct CSV / Parquet Consumption

If connecting without a running PostgreSQL instance (e.g. using the embedded local engine):
1. In the DataNexus UI, navigate to **Intelligence (BI)** or **Data Platform**.
2. Click **Export Invoices CSV** (or download from `/api/data-platform/export/invoices`).
3. In Power BI Desktop, click **Get Data** → **Text/CSV** → Select the exported file.

---

## 4. Star-Schema Semantic Model Relationships

If importing the underlying dimensional tables (`dim_vendor`, `dim_date`, `fact_invoice`, `fact_invoice_line`):

| From Table | From Column | To Table | To Column | Cardinality | Cross Filter |
|---|---|---|---|---|---|
| `fact_invoice` | `vendor_key` | `dim_vendor` | `vendor_key` | Many to One (1:*) | Single |
| `fact_invoice` | `invoice_date_key` | `dim_date` | `date_key` | Many to One (1:*) | Single |
| `fact_invoice` | `due_date_key` | `dim_date` | `date_key` | Many to One (1:*) | Inactive / Single |
| `fact_invoice_line` | `invoice_key` | `fact_invoice` | `invoice_key` | Many to One (1:*) | Single |

---

## 5. Recommended DAX Measures

### A. Total Invoiced Spend (USD)
```dax
Total Invoiced Spend USD = 
CALCULATE(
    SUM(v_invoice_spend_by_vendor[total_spend]),
    v_invoice_spend_by_vendor[currency] = "USD"
)
```

### B. Overdue Liability Exposure
```dax
Total Overdue Exposure = 
SUM(v_overdue_invoices[total_amount])
```

### C. Overdue Invoices Count
```dax
Overdue Invoices Count = 
COUNTROWS(v_overdue_invoices)
```

### D. Data Quality Pass Rate
```dax
Quality Pass Rate % = 
AVERAGE(v_data_quality_scorecard[pass_percentage])
```

### E. Average Document Processing Time (Seconds)
```dax
Avg Processing Time Sec = 
DIVIDE(AVERAGE(v_processing_performance[avg_duration_ms]), 1000)
```

---

## 6. Report Layout Recommendations

### Dashboard A: Executive Spend & Cash Flow
- **KPI Card 1**: Total Spend USD
- **KPI Card 2**: Overdue Liability Amount
- **Bar Chart**: Total Spend by Vendor Category
- **Line Chart**: Monthly Spend Trends
- **Table**: Overdue Invoices ranked by Days Overdue with Document IDs

### Dashboard B: Document Operations & Quality
- **KPI Card 1**: Total Ingested Documents
- **KPI Card 2**: Data Quality Pass Percentage
- **Donut Chart**: Processing Performance by File Format
- **Scorecard Table**: Rule Evaluations (Completeness, Uniqueness, Date Sequence, Currency)
