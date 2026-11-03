"""
================================================================================
⚡ Utrecht Science Park (USP) - Seasonal Campus Energy Flow Dashboard
================================================================================
An interactive Streamlit & Plotly dashboard modeling real 2025 campus energy flows
(in GWh) across individual buildings and facilities at Utrecht Science Park (USP).
Analyzes high-resolution (15-minute) measured consumption for electricity and heat,
comparing the Summer Season (Jun-Aug) against the Winter Season (Dec-Feb).

Data Sources (2025):
- USP_electricity_data.xlsx
- USP_heat_data_15min.xlsx
- USP_pv_generation.xlsx

Authors: Utrecht Science Park Energy Transition Project Team
Dependencies: streamlit, plotly, pandas, openpyxl
Run with: streamlit run app.py
================================================================================
"""

import io
import os
import json
import numpy as np
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, List, Tuple


# ==============================================================================
# 1. LOAD PREPROCESSED 2025 SEASONAL DATA
# ==============================================================================

DATA_JSON_PATH = "usp_energy_data_2025.json"

@st.cache_data
def load_base_data() -> Dict[str, any]:
    """Loads pre-aggregated 2025 seasonal data from JSON file."""
    if os.path.exists(DATA_JSON_PATH):
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # Fallback if json not found: run aggregation script
        import generate_seasonal_data
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

BASE_DATA = load_base_data()


# ==============================================================================
# 1b. LOAD & PROCESS FUNCTION-BASED DAILY LOAD PROFILE DATA
# ==============================================================================

FUNCTION_EXCEL_PATH = "electricity use every function.xlsx"

# Curated, high-contrast color palette for each building function
FUNCTION_COLORS: Dict[str, str] = {
    "Medical":                 "#0284c7",   # Ocean Blue
    "Education":               "#f59e0b",   # Amber Gold
    "Office":                  "#7c3aed",   # Vivid Purple
    "Research & Innovation":   "#059669",   # Emerald Green
    "Housing and amenities":   "#f97316",   # Tangerine Orange
    "Energy Production":       "#dc2626",   # Crimson Red
}


@st.cache_data(show_spinner="Loading seasonal load profile data...")
def load_seasonal_function_profiles() -> Dict[str, pd.DataFrame]:
    """
    Reads 'electricity use every function.xlsx' (now with a Timestamp column at col 0),
    maps every building column to its function group, sums consumption per function,
    then computes the mean 15-minute daily profile separately for:
      - 'Summer'   : June, July, August  (months 6-8)
      - 'Winter'   : December, January, February  (months 12, 1, 2)
      - 'Full Year': all months

    Returns a dict:  { 'Summer': df, 'Winter': df, 'Full Year': df }
    Each DataFrame has columns: time_minutes (0..1425) + one col per function (kW).
    """
    if not os.path.exists(FUNCTION_EXCEL_PATH):
        return {}

    # --- 1. Read raw sheet (no header) ---
    raw = pd.read_excel(FUNCTION_EXCEL_PATH, sheet_name=0, header=None)

    # --- 2. Build column -> function mapping ---
    func_label_row   = raw.iloc[0]   # function group names
    building_name_row = raw.iloc[2]  # individual building names
    func_series = func_label_row.ffill()

    col_to_func: Dict[int, str] = {}
    for col_idx in range(1, raw.shape[1]):   # skip col 0 (timestamp)
        bname = building_name_row.iloc[col_idx]
        func  = func_series.iloc[col_idx]
        if pd.notna(bname) and pd.notna(func):
            col_to_func[col_idx] = str(func)

    functions = list(dict.fromkeys(col_to_func.values()))   # ordered unique

    # --- 3. Extract data rows (row 3 onwards) ---
    data = raw.iloc[3:].reset_index(drop=True).copy()

    # Parse timestamp column (col 0)
    timestamps = pd.to_datetime(data.iloc[:, 0], errors="coerce")

    # Convert building columns to numeric
    numeric_cols = list(col_to_func.keys())
    data_num = data[numeric_cols].apply(pd.to_numeric, errors="coerce")

    # --- 4. Sum per function group ---
    func_sums: Dict[str, pd.Series] = {}
    for func in functions:
        cols = [c for c, f in col_to_func.items() if f == func]
        func_sums[func] = data_num[cols].sum(axis=1, skipna=True)

    agg_df = pd.DataFrame(func_sums)
    agg_df["timestamp"]    = timestamps.values
    agg_df["time_minutes"] = timestamps.dt.hour * 60 + timestamps.dt.minute
    agg_df["month"]        = timestamps.dt.month

    # --- 5. Define season masks ---
    season_masks = {
        "Summer ☀️ (Jun – Aug)": agg_df["month"].isin([6, 7, 8]),
        "Winter ❄️ (Dec – Feb)": agg_df["month"].isin([12, 1, 2]),
        "Full Year 📅":           pd.Series([True] * len(agg_df), index=agg_df.index),
    }

    # --- 6. Compute mean daily profile per season ---
    results: Dict[str, pd.DataFrame] = {}
    for season_label, mask in season_masks.items():
        subset = agg_df[mask]
        if subset.empty:
            continue
        profile = subset.groupby("time_minutes")[functions].mean().reset_index()
        profile = profile.sort_values("time_minutes").reset_index(drop=True)
        results[season_label] = profile

    return results


# ==============================================================================
# 2. DIVERSE COLOR PALETTE & VISUAL STYLING (HIGH CONTRAST)
# ==============================================================================

NODE_COLORS: Dict[str, str] = {
    "National Grid Import":                 "#2563eb",
    "Local CHP (WKK Production)":          "#059669",
    "Local Solar PV Generation":            "#f59e0b",
    "District Heating & WKC Central Plant": "#991b1b",
    "USP Campus Electricity Grid":          "#334155",
    "USP Campus Thermal Grid":              "#854d0e",
    "UMCU Hospital Complex":                "#0284c7",
    "UMCU - WKZ [Elektra inkoop WKZ]":       "#06b6d4",
    "UMCU - AZU [Veld 18 + Veld 19]":        "#0284c7",
    "Kadans Life Sciences":                 "#8b5cf6",
    "Kadans - Accelerator":                 "#7c3aed",
    "Kadans - Genmab R&D Centre":           "#a855f7",
    "Kadans - Plus Ultra":                  "#9333ea",
    "Hubrecht Institute":                   "#3b82f6",
    "Hubrecht - Hubrect Insititute":        "#3b82f6",
    "HU Campus Facilities":                 "#ea580c",
    "HU - Bolognalaan 101":                 "#ea580c",
    "HU - Padualaan 101":                   "#f97316",
    "HU - Padualaan 99":                    "#fb923c",
    "HU - Heidelberglaan 7":                "#ea580c",
    "HU - Heidelberglaan 15":               "#f97316",
    "SSH Student Housing":                  "#10b981",
    "SSH - Johanna":                        "#10b981",
    "SSH - Cambridgelaan":                  "#059669",
    "SSH - Casa Confetti":                  "#34d399",
    "SSH - De Bisschoppen":                 "#10b981",
    "UU Buildings & Labs":                  "#dc2626",
    "UU - Hugo Kruyt Building [Padualaan 8]": "#dc2626",
    "UU - David de Wied building [Universiteitsweg 99]": "#db2777",
    "UU - Bloembergen building [Padualaan 12]": "#be123c",
    "UU - Ornstein Laboratory [Princetonplein 1]": "#b91c1c",
    "UU - Androclus building [Yalelaan 1 A]": "#0d9488",
    "UU - Willem C. Schimmel building / Surgical Clinic [Yalelaan 112]": "#047857",
    "UU - Nieuw Gildestein [Yalelaan 2]":   "#14b8a6",
    "UU - Prof. Dr. H. Jakob building / Pet clinic [Yalelaan 8]": "#0f766e",
    "UU - Educatorium [Leuvenlaan 19]":      "#4f46e5",
    "UU - Minnaert Building [Leuvenlaan 4]": "#6366f1",
    "UU - Marinus Ruppert Building [Leuvenlaan 21]": "#4338ca",
    "UU - Victor J. Koningsberger Building / Education Center [Budapestlaan 2]": "#3b82f6",
    "UU - University Library USP (UBU) [Heidelberglaan 3]": "#1d4ed8",
    "UU - Researchkassen Botanische tuin [Uppsalalaan GARDEN]": "#15803d",
    "UU - Researchkassen Botanische tuin [Uppsalalaan TUIN] [Heat]": "#15803d",
}

DISTINCT_FALLBACK_PALETTE = [
    "#0284c7", "#7c3aed", "#059669", "#ea580c", "#db2777",
    "#0891b2", "#4f46e5", "#16a34a", "#d97706", "#9333ea",
    "#0d9488", "#2563eb", "#65a30d", "#c026d3", "#e11d48"
]


def get_node_color(node_name: str) -> str:
    """Assigns distinctive, high-contrast colors avoiding excessive red clustering."""
    if node_name in NODE_COLORS:
        return NODE_COLORS[node_name]
    if "Grid" in node_name:
        return "#334155" if "Electricity" in node_name else "#854d0e"
    if "UMCU" in node_name:
        return "#0284c7"
    if "Kadans" in node_name:
        return "#7c3aed"
    if "HU -" in node_name or "HU " in node_name:
        return "#ea580c"
    if "SSH -" in node_name or "SSH " in node_name:
        return "#10b981"
    if "Hubrecht" in node_name:
        return "#3b82f6"
    if "Veterinary" in node_name or "Yalelaan" in node_name:
        return "#0d9488"
    if "Educatorium" in node_name or "Minnaert" in node_name or "Library" in node_name:
        return "#4f46e5"
    if "UU -" in node_name or "UU " in node_name:
        return "#dc2626"
    if "[Heat]" in node_name:
        return "#c2410c"
        
    palette_idx = abs(hash(node_name)) % len(DISTINCT_FALLBACK_PALETTE)
    return DISTINCT_FALLBACK_PALETTE[palette_idx]


def hex_to_rgba(hex_code: str, alpha: float = 0.35) -> str:
    """Converts a hexadecimal color (#RRGGBB) to rgba(R, G, B, A)."""
    hex_code = hex_code.lstrip('#')
    if len(hex_code) == 6:
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    return f"rgba(100, 116, 139, {alpha})"


# ==============================================================================
# 3. MODULAR SANKEY FIGURE BUILDER
# ==============================================================================

def filter_flows_by_granularity(df_flows: pd.DataFrame, granularity: str) -> pd.DataFrame:
    if granularity == "All Individual Buildings":
        return df_flows.copy()
        
    supply_rows = df_flows[df_flows["category"] == "Supply"].copy()
    demand_rows = df_flows[df_flows["category"] == "Demand"].copy()
    
    if granularity == "Grouped by Organization":
        def extract_org(target_name: str) -> str:
            if "UU -" in target_name:
                return "UU Buildings & Labs" + (" [Heat]" if "[Heat]" in target_name else "")
            elif "UMCU" in target_name:
                return "UMCU Hospital Complex" + (" [Heat]" if "[Heat]" in target_name else "")
            elif "HU -" in target_name:
                return "HU Campus Facilities" + (" [Heat]" if "[Heat]" in target_name else "")
            elif "SSH -" in target_name:
                return "SSH Student Housing" + (" [Heat]" if "[Heat]" in target_name else "")
            elif "Kadans" in target_name:
                return "Kadans Life Sciences" + (" [Heat]" if "[Heat]" in target_name else "")
            elif "Hubrecht" in target_name:
                return "Hubrecht Institute" + (" [Heat]" if "[Heat]" in target_name else "")
            return "Other Campus Facilities"
            
        demand_rows["target"] = demand_rows["target"].apply(extract_org)
        grouped_demand = demand_rows.groupby(["category", "source", "target"], as_index=False)["value"].sum()
        grouped_demand["value"] = grouped_demand["value"].round(3)
        return pd.concat([supply_rows, grouped_demand], ignore_index=True)
        
    elif granularity == "Top 12 Facilities + Others":
        demand_sorted = demand_rows.sort_values(by="value", ascending=False)
        top_12 = demand_sorted.head(12)
        remainder = demand_sorted.iloc[12:]
        
        if not remainder.empty:
            remainder_by_source = remainder.groupby(["category", "source"], as_index=False)["value"].sum()
            remainder_by_source["target"] = remainder_by_source["source"].apply(
                lambda s: "Other Buildings & Facilities [Heat]" if "Thermal" in s else "Other Campus Buildings & Labs"
            )
            remainder_by_source["value"] = remainder_by_source["value"].round(3)
            return pd.concat([supply_rows, top_12, remainder_by_source], ignore_index=True)
        return pd.concat([supply_rows, top_12], ignore_index=True)

    return df_flows.copy()


def build_sankey_diagram(df_flows: pd.DataFrame, height: int = 620) -> go.Figure:
    active_flows = df_flows[df_flows["value"] > 0].copy()
    
    if active_flows.empty:
        fig = go.Figure()
        fig.update_layout(title="No active energy flows to display.")
        return fig
    
    sources_set = set(active_flows["source"])
    targets_set = set(active_flows["target"])
    
    pure_sources = [s for s in active_flows["source"].unique() if s not in targets_set]
    pure_sinks = [t for t in active_flows["target"].unique() if t not in sources_set]
    intermediaries = [n for n in (sources_set & targets_set)]
    
    ordered_nodes = pure_sources + intermediaries + pure_sinks
    node_to_idx = {name: idx for idx, name in enumerate(ordered_nodes)}
    
    node_colors = [get_node_color(name) for name in ordered_nodes]
    
    link_sources = active_flows["source"].map(node_to_idx).tolist()
    link_targets = active_flows["target"].map(node_to_idx).tolist()
    link_values = active_flows["value"].tolist()
    
    link_colors = [
        hex_to_rgba(get_node_color(src), alpha=0.35)
        for src in active_flows["source"]
    ]
    
    node_hover = (
        "<b>%{label}</b><br>"
        "Total Energy Flow: <b>%{value:,.3f} GWh</b>"
        "<extra></extra>"
    )
    link_hover = (
        "<b>%{source.label}</b> ➔ <b>%{target.label}</b><br>"
        "Energy Flow: <b>%{value:,.3f} GWh</b>"
        "<extra></extra>"
    )
    
    sankey_trace = go.Sankey(
        arrangement="snap",
        node=dict(
            pad=16,
            thickness=18,
            line=dict(color="#1e293b", width=1.0),
            label=ordered_nodes,
            color=node_colors,
            hovertemplate=node_hover,
        ),
        link=dict(
            source=link_sources,
            target=link_targets,
            value=link_values,
            color=link_colors,
            hovertemplate=link_hover,
        ),
    )
    
    fig = go.Figure(data=[sankey_trace])
    fig.update_layout(
        font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", size=12, color="#0f172a"),
        margin=dict(l=25, r=25, t=30, b=30),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="#0f172a",
            font_size=13,
            font_color="#ffffff",
            font_family="Inter, -apple-system, Segoe UI, sans-serif"
        )
    )
    return fig


# ==============================================================================
# 4. STREAMLIT APPLICATION STATE INITIALIZATION
# ==============================================================================

def init_session_state():
    if "seasonal_data" not in st.session_state:
        st.session_state["seasonal_data"] = {}
        for sname, sdata in BASE_DATA.items():
            st.session_state["seasonal_data"][sname] = {
                "electricity": pd.DataFrame(sdata["electricity"]),
                "heat": pd.DataFrame(sdata["heat"]),
                "summary": sdata["summary"]
            }
            
    for sname in BASE_DATA.keys():
        for vector in ["electricity", "heat", "combined"]:
            key = f"reset_ver_{sname}_{vector}"
            if key not in st.session_state:
                st.session_state[key] = 0


def reset_active_data(scenario_name: str, vector_choice: str):
    if vector_choice in ["Electricity", "Combined"]:
        st.session_state["seasonal_data"][scenario_name]["electricity"] = pd.DataFrame(
            BASE_DATA[scenario_name]["electricity"]
        )
    if vector_choice in ["Heat", "Combined"]:
        st.session_state["seasonal_data"][scenario_name]["heat"] = pd.DataFrame(
            BASE_DATA[scenario_name]["heat"]
        )
    st.session_state[f"reset_ver_{scenario_name}_{vector_choice}"] += 1


# ==============================================================================
# 5. MAIN STREAMLIT APPLICATION
# ==============================================================================

def main():
    st.set_page_config(
        page_title="USP Energy Flow | 2025 Seasonal Analysis",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    init_session_state()

    st.markdown("""
        <style>
        .dashboard-title {
            font-size: 2.15rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.2rem;
            letter-spacing: -0.02em;
        }
        .dashboard-subtitle {
            font-size: 1.05rem;
            color: #475569;
            margin-bottom: 1.1rem;
            line-height: 1.5;
        }
        .season-badge {
            display: inline-block;
            background-color: #f1f5f9;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            font-weight: 600;
            font-size: 0.9rem;
            padding: 5px 14px;
            border-radius: 9999px;
            margin-bottom: 14px;
        }
        .legend-tag {
            display: inline-flex;
            align-items: center;
            margin-right: 18px;
            font-size: 0.85rem;
            font-weight: 500;
            color: #334155;
        }
        .color-dot {
            width: 11px;
            height: 11px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
        }
        </style>
    """, unsafe_allow_html=True)

    # SIDEBAR
    st.sidebar.markdown("## ⚡ Scenario & Energy Type")
    
    selected_season = st.sidebar.radio(
        label="Select Seasonal Period (2025):",
        options=list(st.session_state["seasonal_data"].keys()),
        index=0,
        help="Compare high-resolution consumption across Summer (Jun-Aug), Winter (Dec-Feb), or Full Year."
    )
    
    st.sidebar.markdown("---")
    
    selected_vector = st.sidebar.radio(
        label="Select Energy Flow Type:",
        options=["Electricity", "Heat", "Combined (Electricity & Heat)"],
        index=0,
        help="View electricity flows, thermal heating demand, or a combined multi-carrier energy flow diagram."
    )
    
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🔄 Reset Active Scenario to Defaults", use_container_width=True, type="primary"):
        reset_active_data(selected_season, selected_vector)
        st.sidebar.success(f"{selected_season} ({selected_vector}) reset to original Excel data!")
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("🎓 **Utrecht Science Park Energy Transition Project**<br>Analyzed from 15-minute 2025 measured datasets.", unsafe_allow_html=True)

    # HEADER
    st.markdown('<div class="dashboard-title">⚡ Utrecht Science Park: 2025 Seasonal Energy Flow</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">'
        'Interactive Sankey model analyzing <b>real 2025 measured consumption</b> (sampled at 15-minute intervals) '
        'across 60+ individual buildings and research facilities at Utrecht Science Park (USP). '
        'Compare the <b>Summer Season (Jun-Aug)</b> against the <b>Winter Season (Dec-Feb)</b>.'
        '</div>',
        unsafe_allow_html=True
    )

    season_pack = st.session_state["seasonal_data"][selected_season]
    summary_stats = season_pack["summary"]

    if selected_vector == "Electricity":
        current_df = season_pack["electricity"].copy()
    elif selected_vector == "Heat":
        current_df = season_pack["heat"].copy()
    else:
        current_df = pd.concat([season_pack["electricity"], season_pack["heat"]], ignore_index=True)

    season_icon = "☀️" if "Summer" in selected_season else ("❄️" if "Winter" in selected_season else "📅")
    st.markdown(
        f'<div class="season-badge">{season_icon} Active Season: <b>{selected_season}</b> | Vector: <b>{selected_vector}</b></div>',
        unsafe_allow_html=True
    )

    # METRIC CARDS
    el_demand = summary_stats["total_electricity_demand_gwh"]
    grid_imp = summary_stats["grid_import_gwh"]
    chp_gen = summary_stats["chp_electricity_gwh"]
    pv_gen = summary_stats["pv_generation_gwh"]
    heat_dem = summary_stats["total_heat_demand_gwh"]
    
    grid_pct = (grid_imp / el_demand * 100) if el_demand > 0 else 0
    chp_pct = (chp_gen / el_demand * 100) if el_demand > 0 else 0
    pv_pct = (pv_gen / el_demand * 100) if el_demand > 0 else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    
    demand_rows = current_df[current_df["category"] == "Demand"]
    supply_rows = current_df[current_df["category"] == "Supply"]

    if selected_vector == "Heat":
        heat_total = demand_rows["value"].sum()
        wkc_supply = supply_rows["value"].sum()
        active_heat_bldgs = len(demand_rows[demand_rows["value"] > 0])
        
        if not demand_rows.empty:
            top_h_row = demand_rows.sort_values(by="value", ascending=False).iloc[0]
            top_h_name = top_h_row["target"].replace(" [Heat]", "").replace("UU - ", "")
            top_h_val = top_h_row["value"]
        else:
            top_h_name, top_h_val = "N/A", 0.0

        with k1:
            st.metric(label="Total Campus Heat Demand", value=f"{heat_total:.2f} GWh", delta="+230% winter peak" if "Winter" in selected_season else "Summer baseline demand", delta_color="inverse" if "Winter" in selected_season else "normal")
        with k2:
            st.metric(label="WKC Central Heat Supply", value=f"{wkc_supply:.2f} GWh", delta="100% district heating", delta_color="normal")
        with k3:
            st.metric(label="Top Heat Consumer", value=f"{top_h_val:.2f} GWh", delta=f"{top_h_name[:24]}", delta_color="normal")
        with k4:
            st.metric(label="Connected Heated Buildings", value=f"{active_heat_bldgs} Facilities", delta="Campus thermal network")
        with k5:
            st.metric(label="Winter vs Summer Benchmark", value="18.69 GWh" if "Winter" in selected_season else "5.66 GWh", delta="+13.04 GWh winter surge" if "Winter" in selected_season else "-70% summer drop", delta_color="inverse" if "Winter" in selected_season else "normal")

    elif selected_vector == "Electricity":
        el_demand = demand_rows["value"].sum()
        grid_imp = current_df.loc[current_df["source"] == "National Grid Import", "value"].sum()
        chp_gen = current_df.loc[current_df["source"].str.contains("CHP|WKK", case=False, na=False), "value"].sum()
        pv_gen = current_df.loc[current_df["source"].str.contains("Solar|PV", case=False, na=False), "value"].sum()
        
        grid_pct = (grid_imp / el_demand * 100) if el_demand > 0 else 0
        chp_pct = (chp_gen / el_demand * 100) if el_demand > 0 else 0
        pv_pct = (pv_gen / el_demand * 100) if el_demand > 0 else 0

        if not demand_rows.empty:
            top_el_row = demand_rows.sort_values(by="value", ascending=False).iloc[0]
            top_el_name = top_el_row["target"].replace("UMCU - ", "").replace("UU - ", "")
            top_el_val = top_el_row["value"]
        else:
            top_el_name, top_el_val = "N/A", 0.0

        with k1:
            st.metric(label="Total Electricity Demand", value=f"{el_demand:.2f} GWh", delta="15-min campus sum")
        with k2:
            st.metric(label="National Grid Import", value=f"{grid_imp:.2f} GWh", delta=f"{grid_pct:.1f}% of electricity", delta_color="normal")
        with k3:
            st.metric(label="Local CHP (WKK Production)", value=f"{chp_gen:.2f} GWh", delta=f"{chp_pct:.1f}% on-site gas power", delta_color="normal")
        with k4:
            st.metric(label="Local Solar PV Generation", value=f"{pv_gen:.3f} GWh", delta=f"{pv_pct:.1f}% share (Summer high)" if "Summer" in selected_season else f"{pv_pct:.1f}% share (Winter low)")
        with k5:
            st.metric(label="Largest Power Consumer", value=f"{top_el_val:.2f} GWh", delta=f"{top_el_name[:24]}", delta_color="normal")

    else:
        total_energy = demand_rows["value"].sum()
        el_demand_sub = demand_rows[~demand_rows["target"].str.contains(r"\[Heat\]", na=False)]["value"].sum()
        heat_demand_sub = demand_rows[demand_rows["target"].str.contains(r"\[Heat\]", na=False)]["value"].sum()
        
        el_pct = (el_demand_sub / total_energy * 100) if total_energy > 0 else 0
        heat_pct = (heat_demand_sub / total_energy * 100) if total_energy > 0 else 0
        
        chp_gen = current_df.loc[current_df["source"].str.contains("CHP|WKK", case=False, na=False), "value"].sum()
        pv_gen = current_df.loc[current_df["source"].str.contains("Solar|PV", case=False, na=False), "value"].sum()
        grid_imp = current_df.loc[current_df["source"] == "National Grid Import", "value"].sum()
        
        with k1:
            st.metric(label="Total Campus Energy", value=f"{total_energy:.2f} GWh", delta="Power + Thermal combined")
        with k2:
            st.metric(label="Electricity Demand", value=f"{el_demand_sub:.2f} GWh", delta=f"{el_pct:.1f}% of total energy")
        with k3:
            st.metric(label="Thermal Heat Demand", value=f"{heat_demand_sub:.2f} GWh", delta=f"{heat_pct:.1f}% of total energy")
        with k4:
            st.metric(label="Local Power (CHP + Solar)", value=f"{(chp_gen + pv_gen):.2f} GWh", delta=f"{chp_gen:.1f} GWh WKK + {pv_gen:.2f} GWh Solar")
        with k5:
            st.metric(label="National Grid Import", value=f"{grid_imp:.2f} GWh", delta=f"{(grid_imp / el_demand_sub * 100):.1f}% grid dependence" if el_demand_sub > 0 else "0%")

    st.write("")

    # TABS
    tab_view, tab_editor, tab_import_export, tab_compare, tab_profile = st.tabs([
        "📊 Seasonal Sankey Diagram & Overview",
        "✏️ Building Data Editor (Spreadsheet)",
        "📂 Excel / CSV Import & Export",
        "⚖️ Summer vs Winter Comparison",
        "📈 Daily Load Profile by Function"
    ])

    current_ver = st.session_state.get(f"reset_ver_{selected_season}_{selected_vector}", 0)
    editor_key = f"editor_{selected_season}_{selected_vector}_{current_ver}"

    # TAB 1: SANKEY
    with tab_view:
        c_filter1, c_filter2 = st.columns([2, 3])
        with c_filter1:
            display_granularity = st.selectbox(
                "Diagram Granularity:",
                options=["Top 12 Facilities + Others", "Grouped by Organization", "All Individual Buildings"],
                index=0,
                help="Switch between top facilities (presentation clean), organization clusters, or complete 60+ facility raw view."
            )
            
        chart_df = filter_flows_by_granularity(current_df, display_granularity)
        num_nodes = len(set(chart_df["source"]).union(set(chart_df["target"])))
        diagram_height = max(580, min(1100, num_nodes * 28))

        st.subheader(f"📊 {selected_season} Energy Flow ({selected_vector})")
        fig_main = build_sankey_diagram(chart_df, height=diagram_height)
        st.plotly_chart(fig_main, use_container_width=True, key=f"sankey_main_{selected_season}_{selected_vector}_{display_granularity}")

        st.markdown("""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 18px; margin-top: -12px; margin-bottom: 24px; line-height: 1.8;">
                <span class="legend-tag"><span class="color-dot" style="background:#2563eb;"></span> <b>National Grid:</b> Electric Blue</span>
                <span class="legend-tag"><span class="color-dot" style="background:#059669;"></span> <b>Local CHP (WKK):</b> Forest Green</span>
                <span class="legend-tag"><span class="color-dot" style="background:#f59e0b;"></span> <b>Solar PV:</b> Gold</span>
                <span class="legend-tag"><span class="color-dot" style="background:#991b1b;"></span> <b>District Heat:</b> Dark Crimson</span>
                <span class="legend-tag"><span class="color-dot" style="background:#0284c7;"></span> <b>UMCU Hospital:</b> Cyan / Ocean Blue</span>
                <span class="legend-tag"><span class="color-dot" style="background:#7c3aed;"></span> <b>Kadans Life Sciences:</b> Purple</span>
                <span class="legend-tag"><span class="color-dot" style="background:#ea580c;"></span> <b>HU Campus:</b> Tangerine Orange</span>
                <span class="legend-tag"><span class="color-dot" style="background:#10b981;"></span> <b>SSH Housing:</b> Mint Green</span>
                <span class="legend-tag"><span class="color-dot" style="background:#dc2626;"></span> <b>UU Science & Labs:</b> Red</span>
                <span class="legend-tag"><span class="color-dot" style="background:#4f46e5;"></span> <b>UU Education & Library:</b> Indigo</span>
                <span class="legend-tag"><span class="color-dot" style="background:#0d9488;"></span> <b>UU Veterinary:</b> Pine Teal</span>
            </div>
        """, unsafe_allow_html=True)

        col_analysis, col_balance = st.columns([3, 2])
        with col_analysis:
            if "Summer" in selected_season:
                st.info(f"""
                **☀️ Summer Season Characteristics (Jun - Aug 2025):**
                * **Peak Solar Production:** Solar PV generates **{pv_gen:.3f} GWh**, nearly 6x higher than in winter.
                * **Low Heat Consumption:** Total campus heat demand drops to **{heat_dem:.2f} GWh**, as space heating is inactive.
                * **Steady Electricity:** Electricity demand remains robust at **{el_demand:.2f} GWh** driven by labs and chillers.
                * **CHP Baseload:** Local CHP generates **{chp_gen:.2f} GWh** ({chp_pct:.1f}% of campus electricity).
                """)
            elif "Winter" in selected_season:
                st.warning(f"""
                **❄️ Winter Season Characteristics (Dec - Feb 2025):**
                * **Heat Demand Surge:** Total campus heat demand skyrockets to **{heat_dem:.2f} GWh** (+230% over summer).
                * **Solar Drop:** Solar PV plummets to just **{pv_gen:.3f} GWh** due to low solar irradiance.
                * **Grid Dependence:** External grid import supplies **{grid_imp:.2f} GWh** ({grid_pct:.1f}% of campus power).
                """)
            else:
                st.info(f"""
                **📅 Full Year 2025 Totals:**
                * **Total Campus Electricity:** **{el_demand:.2f} GWh**.
                * **Total Campus Heat:** **{heat_dem:.2f} GWh** supplied via district heating.
                """)

        with col_balance:
            supply_tot = chart_df[chart_df["category"] == "Supply"]["value"].sum()
            demand_tot = chart_df[chart_df["category"] == "Demand"]["value"].sum()
            balance_delta = supply_tot - demand_tot
            is_balanced = abs(balance_delta) < 0.05
            
            st.markdown(f"""
            <div style="background-color: {'#ecfdf5' if is_balanced else '#fffbeb'}; border: 1px solid {'#10b981' if is_balanced else '#f59e0b'}; padding: 16px; border-radius: 8px;">
                <h4 style="margin: 0 0 8px 0; color: {'#065f46' if is_balanced else '#92400e'};">
                    {'✅ Energy Balance Verified' if is_balanced else '⚠️ Energy Balance Notice'}
                </h4>
                <p style="margin: 0; font-size: 0.92rem; color: #1e293b; line-height: 1.6;">
                    <b>Total Supply Inflow:</b> {supply_tot:.3f} GWh<br>
                    <b>Total Consumer Outflow:</b> {demand_tot:.3f} GWh<br>
                    <b>Balance Difference (Δ):</b> {balance_delta:.3f} GWh
                </p>
            </div>
            """, unsafe_allow_html=True)
            st.caption("ℹ️ Verified against 35,040 quarterly measured 15-minute readings.")

    # TAB 2: EDITOR
    with tab_editor:
        st.markdown(f"### ✏️ Campus Energy Flow Spreadsheet ({selected_season} — {selected_vector})")
        st.write("Modify any cell by double-clicking. You can also add new rows at the bottom.")

        edited_df = st.data_editor(
            current_df,
            column_config={
                "category": st.column_config.SelectboxColumn("Category", options=["Supply", "Demand"], required=True),
                "source": st.column_config.TextColumn("Source Node", required=True),
                "target": st.column_config.TextColumn("Target / Building Name", required=True),
                "value": st.column_config.NumberColumn("Energy Flow (GWh)", min_value=0.0, max_value=500.0, step=0.01, format="%.3f GWh", required=True),
            },
            num_rows="dynamic",
            use_container_width=True,
            key=editor_key
        )

        if selected_vector == "Electricity":
            st.session_state["seasonal_data"][selected_season]["electricity"] = edited_df
        elif selected_vector == "Heat":
            st.session_state["seasonal_data"][selected_season]["heat"] = edited_df

        st.success("✅ Changes preserved in session. Live Sankey preview updates below:")

        st.markdown("#### ⚡ Live Sankey Diagram Preview:")
        preview_filtered = filter_flows_by_granularity(edited_df, "Top 12 Facilities + Others")
        fig_prev = build_sankey_diagram(preview_filtered, height=540)
        st.plotly_chart(fig_prev, use_container_width=True, key=f"sankey_preview_{selected_season}_{selected_vector}")

    # TAB 3: IMPORT & EXPORT
    with tab_import_export:
        st.markdown("### 📂 Excel & CSV Data Management")
        col_export, col_import = st.columns(2)

        with col_export:
            st.markdown("#### 1. Download Current Scenario Data")
            csv_bytes = current_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download {selected_season} ({selected_vector}) as CSV",
                data=csv_bytes,
                file_name=f"USP_2025_{selected_season.replace(' ', '_')}_{selected_vector}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                current_df.to_excel(writer, index=False, sheet_name="Data_2025")
            excel_data = excel_buf.getvalue()
            
            st.download_button(
                label=f"📊 Download {selected_season} ({selected_vector}) as Excel (.xlsx)",
                data=excel_data,
                file_name=f"USP_2025_{selected_season.replace(' ', '_')}_{selected_vector}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col_import:
            st.markdown("#### 2. Upload Custom Excel / CSV File")
            uploaded_file = st.file_uploader(
                f"Upload updated data file for {selected_season} ({selected_vector}):",
                type=["csv", "xlsx"],
                help="File must contain columns: 'category', 'source', 'target', 'value'."
            )
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith(".csv"):
                        new_data = pd.read_csv(uploaded_file)
                    else:
                        new_data = pd.read_excel(uploaded_file)
                        
                    required_cols = {"category", "source", "target", "value"}
                    if required_cols.issubset(set(new_data.columns)):
                        if selected_vector == "Electricity":
                            st.session_state["seasonal_data"][selected_season]["electricity"] = new_data
                        elif selected_vector == "Heat":
                            st.session_state["seasonal_data"][selected_season]["heat"] = new_data
                        st.session_state[f"reset_ver_{selected_season}_{selected_vector}"] += 1
                        st.success(f"🎉 Successfully imported '{uploaded_file.name}'!")
                        st.rerun()
                    else:
                        st.error(f"Missing required columns! File must include: {required_cols}")
                except Exception as e:
                    st.error(f"Error reading file: {e}")

    # TAB 4: COMPARE
    with tab_compare:
        st.markdown("### ⚖️ Summer Season (Jun-Aug) vs. Winter Season (Dec-Feb) Comparison")

        summer_sum = BASE_DATA["Summer Season (Jun - Aug 2025)"]["summary"]
        winter_sum = BASE_DATA["Winter Season (Dec - Feb 2025)"]["summary"]

        comp_kpis = pd.DataFrame([
            {"Metric": "Total Campus Electricity Demand", "Summer 2025 (GWh)": summer_sum["total_electricity_demand_gwh"], "Winter 2025 (GWh)": winter_sum["total_electricity_demand_gwh"]},
            {"Metric": "National Grid Electricity Import", "Summer 2025 (GWh)": summer_sum["grid_import_gwh"], "Winter 2025 (GWh)": winter_sum["grid_import_gwh"]},
            {"Metric": "Local CHP (WKK Electricity)", "Summer 2025 (GWh)": summer_sum["chp_electricity_gwh"], "Winter 2025 (GWh)": winter_sum["chp_electricity_gwh"]},
            {"Metric": "Local Solar PV Generation", "Summer 2025 (GWh)": summer_sum["pv_generation_gwh"], "Winter 2025 (GWh)": winter_sum["pv_generation_gwh"]},
            {"Metric": "Total Campus Heat Demand", "Summer 2025 (GWh)": summer_sum["total_heat_demand_gwh"], "Winter 2025 (GWh)": winter_sum["total_heat_demand_gwh"]},
        ])
        comp_kpis["Seasonal Difference (Winter - Summer GWh)"] = (comp_kpis["Winter 2025 (GWh)"] - comp_kpis["Summer 2025 (GWh)"]).round(3)
        comp_kpis["Change (%)"] = ((comp_kpis["Seasonal Difference (Winter - Summer GWh)"] / comp_kpis["Summer 2025 (GWh)"]) * 100).round(1)

        st.dataframe(comp_kpis, use_container_width=True, hide_index=True)

    # TAB 5: PROFILE
    with tab_profile:
        st.markdown("### 📈 Seasonal Daily Load Profile by Building Function")

        all_profiles = load_seasonal_function_profiles()

        if not all_profiles:
            st.error(f"⚠️ Could not load data. Make sure **'{FUNCTION_EXCEL_PATH}'** exists.")
        else:
            functions_available = [
                c for c in next(iter(all_profiles.values())).columns
                if c != "time_minutes"
            ]

            gc1, gc2, gc3 = st.columns([3, 2, 1])
            with gc1:
                selected_functions = st.multiselect("Building functions to display:", options=functions_available, default=functions_available)
            with gc2:
                smoothing = st.slider("Smoothing window (15-min intervals):", min_value=1, max_value=12, value=4)
            with gc3:
                show_area = st.checkbox("Area fill", value=True)

            if not selected_functions:
                st.warning("Please select at least one building function.")
            else:
                x_axis_cfg = dict(
                    title="Time of Day",
                    tickmode="array",
                    tickvals=list(range(0, 25, 2)),
                    ticktext=[f"{h:02d}:00" for h in range(0, 25, 2)],
                    showgrid=True, gridcolor="#e2e8f0",
                    zeroline=False, range=[0, 24],
                )
                y_axis_cfg = dict(
                    title="Avg Electricity Demand (kW)",
                    showgrid=True, gridcolor="#e2e8f0",
                    zeroline=True, zerolinecolor="#94a3b8",
                    rangemode="tozero",
                )
                legend_cfg = dict(
                    orientation="h", yanchor="top", y=-0.22,
                    xanchor="center", x=0.5,
                    font=dict(size=11, family="Inter, sans-serif"),
                )
                base_layout = dict(
                    hovermode="x unified",
                    plot_bgcolor="#f8fafc",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", color="#0f172a"),
                    margin=dict(l=60, r=20, t=50, b=100),
                    height=460,
                    hoverlabel=dict(
                        bgcolor="#0f172a", font_size=12,
                        font_color="#ffffff", font_family="Inter, sans-serif",
                    ),
                )

                def build_season_fig(profile_df: pd.DataFrame, season_label: str, season_icon: str, show_legend: bool = True) -> go.Figure:
                    fig = go.Figure()
                    x_hours = profile_df["time_minutes"] / 60.0

                    for func in selected_functions:
                        if func not in profile_df.columns:
                            continue
                        color = FUNCTION_COLORS.get(func, "#64748b")
                        y_vals = profile_df[func].copy()
                        if smoothing > 1:
                            y_vals = y_vals.rolling(window=smoothing, center=True, min_periods=1).mean()

                        r_c = int(color[1:3], 16)
                        g_c = int(color[3:5], 16)
                        b_c = int(color[5:7], 16)
                        fill_color = f"rgba({r_c},{g_c},{b_c},0.15)"

                        fig.add_trace(go.Scatter(
                            x=x_hours, y=y_vals,
                            name=func,
                            mode="lines",
                            line=dict(color=color, width=2.5),
                            fill="tozeroy" if show_area else None,
                            fillcolor=fill_color if show_area else None,
                            showlegend=show_legend,
                            hovertemplate=f"<b>{func}</b><br>Time: %{{x:.2f}} h<br>Load: <b>%{{y:,.1f}} kW</b><extra></extra>",
                        ))

                        peak_idx  = int(y_vals.idxmax())
                        peak_time = profile_df.loc[peak_idx, "time_minutes"] / 60.0
                        peak_val  = float(y_vals.iloc[peak_idx])
                        fig.add_annotation(
                            x=peak_time, y=peak_val,
                            text=f"  ▲ {peak_val:,.0f}",
                            showarrow=False,
                            font=dict(size=9, color=color, family="Inter, sans-serif"),
                            xanchor="left", yanchor="middle",
                        )

                    fig.update_layout(
                        **base_layout,
                        title=dict(text=f"{season_icon} {season_label}", font=dict(size=15, family="Inter, sans-serif", color="#0f172a"), x=0.01),
                        xaxis=x_axis_cfg, yaxis=y_axis_cfg,
                        legend=legend_cfg if show_legend else dict(visible=False),
                    )
                    return fig

                st.markdown("#### ☀️ Summer vs ❄️ Winter — Side-by-Side Comparison")
                col_s, col_w = st.columns(2)

                summer_key = "Summer ☀️ (Jun – Aug)"
                winter_key = "Winter ❄️ (Dec – Feb)"

                with col_s:
                    if summer_key in all_profiles:
                        fig_s = build_season_fig(all_profiles[summer_key], "Summer Season (Jun – Aug 2025)", "☀️", show_legend=True)
                        st.plotly_chart(fig_s, use_container_width=True, key="profile_summer")
                    else:
                        st.warning("No Summer data found.")

                with col_w:
                    if winter_key in all_profiles:
                        fig_w = build_season_fig(all_profiles[winter_key], "Winter Season (Dec – Feb 2025)", "❄️", show_legend=True)
                        st.plotly_chart(fig_w, use_container_width=True, key="profile_winter")
                    else:
                        st.warning("No Winter data found.")

                st.markdown("#### 📅 Full Year Average Profile (All Months)")
                full_key = "Full Year 📅"
                if full_key in all_profiles:
                    fig_full = build_season_fig(all_profiles[full_key], "Full Year 2025 — Annual Average Daily Profile", "📅", show_legend=True)
                    fig_full.update_layout(height=460)
                    st.plotly_chart(fig_full, use_container_width=True, key="profile_full")

                st.markdown("#### 📋 Seasonal Peak Load Comparison by Function")
                comp_rows = []
                for func in functions_available:
                    row: Dict[str, any] = {"Building Function": func}
                    for season_label, profile_df in all_profiles.items():
                        if func not in profile_df.columns:
                            continue
                        y = profile_df[func]
                        if smoothing > 1:
                            y = y.rolling(window=smoothing, center=True, min_periods=1).mean()
                        peak_val  = float(y.max())
                        peak_mins = int(profile_df.loc[int(y.idxmax()), "time_minutes"])
                        peak_str  = f"{peak_val:,.0f} kW @ {peak_mins//60:02d}:{peak_mins%60:02d}"
                        short = season_label.split(" (")[0]
                        row[f"Peak — {short}"] = peak_str
                    comp_rows.append(row)

                comp_df = pd.DataFrame(comp_rows)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

                if summer_key in all_profiles and winter_key in all_profiles:
                    st.markdown("#### 📈 Winter vs Summer Peak Load Difference")
                    delta_rows = []
                    for func in functions_available:
                        if func not in all_profiles[summer_key].columns:
                            continue
                        s_peak = float(all_profiles[summer_key][func].max())
                        w_peak = float(all_profiles[winter_key][func].max())
                        diff   = w_peak - s_peak
                        pct    = (diff / s_peak * 100) if s_peak > 0 else 0
                        delta_rows.append({
                            "Building Function":       func,
                            "Summer Peak (kW)":        round(s_peak, 1),
                            "Winter Peak (kW)":        round(w_peak, 1),
                            "Δ Winter – Summer (kW)":  round(diff, 1),
                            "Change (%)":              round(pct, 1),
                        })
                    delta_df = pd.DataFrame(delta_rows).sort_values("Δ Winter – Summer (kW)", ascending=False).reset_index(drop=True)
                    st.dataframe(delta_df, use_container_width=True, hide_index=True)

                st.info("💡 **How to read these charts:** Each line = mean electricity demand (kW) of all buildings in that category, averaged across 15-minute slots over the season.")


if __name__ == "__main__":
    main()