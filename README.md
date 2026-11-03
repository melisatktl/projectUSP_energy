# ⚡ Utrecht Science Park (USP) - Seasonal Energy Flow Dashboard (2025)

An interactive Streamlit & Plotly dashboard modeling **real 2025 campus energy flows** (in GWh) across individual buildings and facilities at the **Utrecht Science Park (USP)**. Analyzes measured 15-minute consumption data for electricity, heat, and solar PV generation, comparing the **Summer Season (Jun-Aug)** against the **Winter Season (Dec-Feb)**.

---

## 📂 Data Sources Analyzed (`datas/`)

1. **`USP_electricity_data.xlsx` (2025):** 35,040 quarterly readings across 73 columns, covering electricity consumption across UU buildings, UMCU Hospital (AZU & WKZ), Hogeschool Utrecht (HU), SSH student housing, Kadans Life Sciences, and local Combined Heat & Power (WKK-1, WKK-2, WKK-3) generation.
2. **`USP_heat_data_15min.xlsx` (2025):** 35,040 quarterly readings across 31 columns, covering district heat consumption across university laboratories, clinical faculties, and central district heating supply from the WKC plant.
3. **`USP_pv_generation.xlsx` (2025):** 35,040 quarterly readings covering 16 rooftop and carport solar PV installations.

---

## 🚀 Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🎯 Key Features

1. **Seasonal Comparison (Sidebar Toggle):**
   - ☀️ **Summer Season (Jun - Aug 2025):** Solar generation peaks at **0.736 GWh** (~6x higher than winter), while campus heat demand drops to **5.655 GWh**. Electricity demand is **19.166 GWh** (chillers, research computing, lab ventilation).
   - ❄️ **Winter Season (Dec - Feb 2025):** Campus heat demand surges to **18.694 GWh** (+230% increase), while solar PV plummets to **0.129 GWh**. Grid imports supply **9.395 GWh** alongside local CHP (**9.150 GWh**).
   - 📅 **Full Year 2025 (Annual Total):** Annual overview covering **74.336 GWh** of electricity demand and **44.017 GWh** of heat demand.
2. **Energy Vector Filter:**
   - ⚡ **Electricity Flow (GWh):** Sources (Grid, Local CHP WKK, Solar PV) $\rightarrow$ Campus Electricity Grid $\rightarrow$ Individual Facilities.
   - 🔥 **Heat Demand Flow (GWh):** WKC Central Plant $\rightarrow$ Campus Thermal Grid $\rightarrow$ Individual Buildings.
   - 🔄 **Combined Energy Flow:** Integrated multi-carrier Sankey diagram.
3. **Diagram Granularity Selector:**
   - **Top 12 Facilities + Others:** Clean, presentation-ready layout.
   - **Grouped by Organization:** High-level overview by institution (UU, UMCU, HU, SSH, Kadans, Hubrecht).
   - **All Individual Buildings:** Complete raw breakdown across 60+ individual facilities.
4. **Interactive Spreadsheet Data Editor:**
   - Live editable table loaded with all real building names and measured 2025 seasonal GWh numbers.
   - Live Sankey preview directly below the table updates in real time.
   - One-click export to **Excel (`.xlsx`)** or **CSV**, plus external file upload.
