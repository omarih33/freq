
import pandas as pd
import streamlit as st
import re

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

# ----------- URL state -----------
params = st.query_params
default_q = params.get("q", [""])[0]
default_cat = params.get("cat", ["(any)"])[0]

# ----------- UI -----------
c1, c2 = st.columns([3,1])
with c1:
    q = st.text_input("Search words", value=default_q, placeholder="e.g., love fast dance", key="q")
with c2:
    cats = ["(any)"] + sorted([c for c in df[CATEGORY_COL].dropna().unique().tolist()])
    cat = st.selectbox("Category", options=cats, index=cats.index(default_cat) if default_cat in cats else 0)

# keep URL synced
st.query_params.update({"q": q, "cat": cat})

# Optional: numeric filter for frequency
with st.expander("More filters", expanded=False):
    fmin, fmax = float(df[FREQ_COL].min()), float(df[FREQ_COL].max())
    freq_range = st.slider("Frequency range", min_value=fmin, max_value=fmax, value=(fmin, fmax))

# ----------- Filtering -----------
res = df
# category
if cat != "(any)":
    res = res[res[CATEGORY_COL] == cat]

# frequency range
res = res[(res[FREQ_COL] >= freq_range[0]) & (res[FREQ_COL] <= freq_range[1])]

# text query: AND over terms; search in WORDS only
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
show = res[[SEARCH_COL, CATEGORY_COL, FREQ_COL, NUM_COL]].head(MAX_RESULTS)
for _, row in show.iterrows():
    st.markdown(f"### {row[SEARCH_COL]}")
    st.markdown(f"**Category:** {row[CATEGORY_COL]} &nbsp;&nbsp;|&nbsp;&nbsp; **Frequency:** {row[FREQ_COL]} &nbsp;&nbsp;|&nbsp;&nbsp; **#:** {row[NUM_COL]}")
    st.divider()

# Table view toggle
with st.expander("Table view", expanded=False):
    st.dataframe(show, use_container_width=True, height=420)

# Download filtered subset
st.download_button("Download results as CSV", show.to_csv(index=False).encode("utf-8"), "lexicon_results.csv", "text/csv")
