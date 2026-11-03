"""
Aggregates 2025 15-minute raw datasets into clean seasonal datasets for Utrecht Science Park.
Generates: usp_energy_data_2025.json
"""

import openpyxl, os, json
import pandas as pd
import numpy as np

print("Aggregating 2025 energy data by season...")

# ------------------------------------------------------------------------------
# 1. READ SOLAR PV
# ------------------------------------------------------------------------------
wb_pv = openpyxl.load_workbook(os.path.join('datas', 'USP_pv_generation.xlsx'), read_only=True, data_only=True)
sheet_pv = wb_pv['2025']
rows_pv = sheet_pv.iter_rows(values_only=True)
next(rows_pv)
org_pv = next(rows_pv)
name_pv = next(rows_pv)

pv_cols = []
curr_org = 'UU'
for i in range(1, len(name_pv)):
    if i < len(org_pv) and org_pv[i]:
        curr_org = str(org_pv[i]).strip().replace('\n', ' ')
    bname = str(name_pv[i]).strip().replace('\n', ' ') if name_pv[i] else f'PV_{i}'
    pv_cols.append((i, curr_org, bname))

pv_data = {f"{o} - {n}": [] for i, o, n in pv_cols}
pv_timestamps = []
for r in rows_pv:
    if r[0] is not None:
        pv_timestamps.append(r[0])
        for i, o, n in pv_cols:
            pv_data[f"{o} - {n}"].append(float(r[i]) if i < len(r) and r[i] is not None else 0.0)

df_pv = pd.DataFrame(pv_data)
df_pv.index = pd.to_datetime(pv_timestamps, errors='coerce')

# ------------------------------------------------------------------------------
# 2. READ HEAT
# ------------------------------------------------------------------------------
wb_ht = openpyxl.load_workbook(os.path.join('datas', 'USP_heat_data_15min.xlsx'), read_only=True, data_only=True)
sheet_ht = wb_ht['2025']
rows_ht = sheet_ht.iter_rows(values_only=True)
next(rows_ht)
org_ht = next(rows_ht)
name_ht = next(rows_ht)

ht_cols = []
curr_org = 'UU'
for i in range(1, len(name_ht)):
    if i < len(org_ht) and org_ht[i]:
        curr_org = str(org_ht[i]).strip().replace('\n', ' ')
    bname = str(name_ht[i]).strip().replace('\n', ' ') if name_ht[i] else f'Heat_{i}'
    ht_cols.append((i, curr_org, bname))

ht_data = {f"{o} - {n}": [] for i, o, n in ht_cols}
ht_timestamps = []
for r in rows_ht:
    if r[0] is not None:
        ht_timestamps.append(r[0])
        for i, o, n in ht_cols:
            ht_data[f"{o} - {n}"].append(float(r[i]) if i < len(r) and r[i] is not None else 0.0)

df_ht = pd.DataFrame(ht_data)
df_ht.index = pd.to_datetime(ht_timestamps, errors='coerce')

# ------------------------------------------------------------------------------
# 3. READ ELECTRICITY
# ------------------------------------------------------------------------------
wb_el = openpyxl.load_workbook(os.path.join('datas', 'USP_electricity_data.xlsx'), read_only=True, data_only=True)
sheet_el = wb_el['2025']
rows_el = sheet_el.iter_rows(values_only=True)
next(rows_el)
org_el = next(rows_el)
name_el = next(rows_el)

el_cols = []
curr_org = 'UU'
for i in range(1, len(name_el)):
    if i < len(org_el) and org_el[i]:
        curr_org = str(org_el[i]).strip().replace('\n', ' ')
    bname = str(name_el[i]).strip().replace('\n', ' ') if name_el[i] else f'El_{i}'
    el_cols.append((i, curr_org, bname))

el_data = {f"{o} - {n}": [] for i, o, n in el_cols}
el_timestamps = []
for r in rows_el:
    if r[0] is not None:
        el_timestamps.append(r[0])
        for i, o, n in el_cols:
            el_data[f"{o} - {n}"].append(float(r[i]) if i < len(r) and r[i] is not None else 0.0)

df_el = pd.DataFrame(el_data)
df_el.index = pd.to_datetime(el_timestamps, errors='coerce')

print("All raw tables loaded into pandas.")

# ------------------------------------------------------------------------------
# 4. COMPUTE SEASONAL AGGREGATES
# ------------------------------------------------------------------------------
seasons = {
    "Summer Season (Jun - Aug 2025)": [6, 7, 8],
    "Winter Season (Dec - Feb 2025)": [12, 1, 2],
    "Full Year 2025 (Annual Total)": list(range(1, 13))
}

results = {}

for season_name, months in seasons.items():
    sub_el = df_el[df_el.index.month.isin(months)]
    sub_pv = df_pv[df_pv.index.month.isin(months)]
    sub_ht = df_ht[df_ht.index.month.isin(months)]
    
    # Identify WKK columns in electricity
    wkk_cols = [c for c in sub_el.columns if "WKK" in c or ("CHP" in c and "Production" in c)]
    # All other columns are consumption buildings
    consumer_cols = [c for c in sub_el.columns if c not in wkk_cols and "Combined Heat and Power Plant" not in c and "Col_72" not in c]
    
    # 1. Total Generation
    wkk_gwh = float(sub_el[wkk_cols].sum().sum() / 1e6)
    pv_gwh = float(sub_pv.sum().sum() / 1e6)
    
    # 2. Building electricity consumption
    b_el_totals = {}
    for c in consumer_cols:
        val = float(sub_el[c].sum() / 1e6)
        if val > 0.001:  # filter negligible < 1 MWh
            # Clean up display name
            clean_name = c.replace("None - ", "").replace("\n", " ")
            b_el_totals[clean_name] = round(val, 3)
            
    total_demand_gwh = sum(b_el_totals.values())
    grid_import_gwh = max(0.0, total_demand_gwh - (wkk_gwh + pv_gwh))
    
    # Format electricity flows
    el_flows = [
        {"category": "Supply", "source": "National Grid Import", "target": "USP Campus Electricity Grid", "value": round(grid_import_gwh, 3)},
        {"category": "Supply", "source": "Local CHP (WKK Production)", "target": "USP Campus Electricity Grid", "value": round(wkk_gwh, 3)},
        {"category": "Supply", "source": "Local Solar PV Generation", "target": "USP Campus Electricity Grid", "value": round(pv_gwh, 3)},
    ]
    for bname, val in sorted(b_el_totals.items(), key=lambda x: x[1], reverse=True):
        el_flows.append({
            "category": "Demand",
            "source": "USP Campus Electricity Grid",
            "target": bname,
            "value": val
        })
        
    # 3. Building Heat Consumption
    b_ht_totals = {}
    ht_producer_cols = [c for c in sub_ht.columns if "Warmte Kracht Centrale" in c or "WKC" in c or "Ketelhuis" in c]
    ht_consumer_cols = [c for c in sub_ht.columns if c not in ht_producer_cols]
    
    for c in ht_consumer_cols:
        val = float(sub_ht[c].sum() / 1e6)
        if val > 0.001:
            clean_name = c.replace("None - ", "").replace("\n", " ")
            b_ht_totals[clean_name] = round(val, 3)
            
    total_heat_demand = sum(b_ht_totals.values())
    ht_flows = [
        {"category": "Supply", "source": "District Heating & WKC Central Plant", "target": "USP Campus Thermal Grid", "value": round(total_heat_demand, 3)},
    ]
    for bname, val in sorted(b_ht_totals.items(), key=lambda x: x[1], reverse=True):
        ht_flows.append({
            "category": "Demand",
            "source": "USP Campus Thermal Grid",
            "target": f"{bname} [Heat]",
            "value": val
        })
        
    results[season_name] = {
        "electricity": el_flows,
        "heat": ht_flows,
        "summary": {
            "total_electricity_demand_gwh": round(total_demand_gwh, 3),
            "grid_import_gwh": round(grid_import_gwh, 3),
            "chp_electricity_gwh": round(wkk_gwh, 3),
            "pv_generation_gwh": round(pv_gwh, 3),
            "total_heat_demand_gwh": round(total_heat_demand, 3),
        }
    }

with open("usp_energy_data_2025.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Data processing complete! Saved to usp_energy_data_2025.json")
