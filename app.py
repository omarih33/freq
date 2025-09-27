
import pandas as pd
import streamlit as st
import re
from typing import List

st.set_page_config(page_title="Lexicon Search", layout="wide")

# ----------- Minimal styling for embed -----------
st.markdown('''
<style>
#MainMenu, header, footer {visibility: hidden;}
.block-container {padding-top: 0.75rem; padding-bottom: 0.5rem;}
</style>
''', unsafe_allow_html=True)

# ----------- Settings -----------
CSV_PATH = st.secrets.get("CSV_PATH", "lexicon.csv")  # place your CSV next to app as 'lexicon.csv'
MAX_RESULTS = 200
CASE_SENSITIVE = False

SEARCH_COL = "WORDS"
CATEGORY_COL = "CATEGORY"
FREQ_COL = "FREQUENCY"
NUM_COL = "NUMBER"

# ----------- Data load (cached) -----------
@st.cache_data
def load_data(path):
    return pd.read_csv(path, dtype_backend="pyarrow", low_memory=False)

try:
    df = load_data(CSV_PATH)
except FileNotFoundError:
    st.error(f"CSV not found at '{CSV_PATH}'. Upload 'lexicon.csv' or set st.secrets['CSV_PATH'].")
    st.stop()

# Sanity: ensure expected columns exist
expected = {SEARCH_COL, CATEGORY_COL, FREQ_COL, NUM_COL}
if not expected.issubset(df.columns):
    st.error(f"Missing columns. Expected: {sorted(expected)}. Found: {sorted(df.columns)}")
    st.stop()

# ----------- URL params (compat across Streamlit versions) -----------
def get_param_list(key: str) -> List[str]:
    # New API returns a QueryParams obj; old returns dict[str, List[str]]
    try:
        qp = st.query_params
        val = qp.get(key, None)
        if val is None:
            return []
        if isinstance(val, (list, tuple)):
            return list(val)
        return [str(val)]
    except Exception:
        qp = st.experimental_get_query_params()
        return qp.get(key, [])

def set_params(**kwargs):
    try:
        # New API (Streamlit >= 1.35)
        st.query_params.update(kwargs)
    except Exception:
        # Old API
        st.experimental_set_query_params(**kwargs)

default_q = get_param_list("q")[0] if get_param_list("q") else ""
default_cat = get_param_list("cat")[0] if get_param_list("cat") else "(any)"

# ----------- UI -----------
c1, c2 = st.columns([3,1])
with c1:
    q = st.text_input("Search words", value=default_q, placeholder="e.g., love fast dance", key="q")
with c2:
    cats = ["(any)"] + sorted([c for c in df[CATEGORY_COL].dropna().unique().tolist()])
    # Protect against invalid default
    try:
        idx = cats.index(default_cat)
    except ValueError:
        idx = 0
    cat = st.selectbox("Category", options=cats, index=idx)

# keep URL synced
set_params(q=q, cat=cat)

# Optional: numeric filter for frequency
with st.expander("More filters", expanded=False):
    # Cast to numeric in case CSV has strings
    freq_series = pd.to_numeric(df[FREQ_COL], errors="coerce")
    fmin, fmax = float(freq_series.min()), float(freq_series.max())
    freq_range = st.slider("Frequency range", min_value=fmin, max_value=fmax, value=(fmin, fmax))

# ----------- Filtering -----------
res = df.copy()
# Frequency first (use numeric series)
res = res[(pd.to_numeric(res[FREQ_COL], errors="coerce") >= freq_range[0]) & (pd.to_numeric(res[FREQ_COL], errors="coerce") <= freq_range[1])]

# Category
if cat != "(any)":
    res = res[res[CATEGORY_COL] == cat]

# Text query: AND over terms; search in WORDS only
query = q.strip()
if query:
    terms = [t for t in re.split(r"\s+", query) if t]
    if terms:
        if CASE_SENSITIVE:
            s = res[SEARCH_COL].astype("string[pyarrow]", copy=False)
            mask = pd.Series([True] * len(res))
            for term in terms:
                hit = s.str.contains(term, na=False, regex=False)
                mask = mask & hit
        else:
            s = res[SEARCH_COL].astype("string[pyarrow]", copy=False).str.lower()
            mask = pd.Series([True] * len(res))
            for term in terms:
                hit = s.str.contains(term.lower(), na=False, regex=False)
                mask = mask & hit
        res = res[mask]

count = len(res)
st.caption(f"{count:,} match(es)")

# ----------- Results (card style) -----------
show_cols = [c for c in [SEARCH_COL, CATEGORY_COL, FREQ_COL, NUM_COL] if c in res.columns]
show = res[show_cols].head(MAX_RESULTS)
for _, row in show.iterrows():
    word = row.get(SEARCH_COL, "")
    catv = row.get(CATEGORY_COL, "")
    freqv = row.get(FREQ_COL, "")
    numv = row.get(NUM_COL, "")
    st.markdown(f"### {word}")
    st.markdown(f"**Category:** {catv} &nbsp;&nbsp;|&nbsp;&nbsp; **Frequency:** {freqv} &nbsp;&nbsp;|&nbsp;&nbsp; **#:** {numv}")
    st.divider()

# Table view toggle
with st.expander("Table view", expanded=False):
    st.dataframe(show, use_container_width=True, height=420)

# Download filtered subset
st.download_button("Download results as CSV", show.to_csv(index=False).encode("utf-8"), "lexicon_results.csv", "text/csv")
