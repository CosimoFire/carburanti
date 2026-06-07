"""
update_map_regioni.py
Scarica il CSV ufficiale MIMIT con le medie regionali
e aggiorna una mappa Datawrapper via API.

CSV: https://www.mimit.gov.it/images/stories/carburanti/MediaRegionaleStradale.csv
"""

import os
import sys
import requests
import pandas as pd
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── CONFIG ─────────────────────────────────────────────────────────────────────
MIMIT_URL = "https://www.mimit.gov.it/images/stories/carburanti/MediaRegionaleStradale.csv"
ENCODING  = "latin-1"

FUEL_ID      = int(os.environ.get("FUEL_ID", "1"))
SELF_SERVICE = int(os.environ.get("SELF_SERVICE", "1"))

DW_API_KEY  = os.environ["DW_API_KEY"]
DW_CHART_ID = os.environ["DW_CHART_ID"]
DW_BASE     = "https://api.datawrapper.de/v3"

TIMEOUT = 30

FUEL_NAMES = {
    1: "Benzina",
    2: "Gasolio",
    3: "GPL",
    5: "Metano",
}

FUEL_LABELS = {
    1: "Benzina",
    2: "Gasolio",
    3: "GPL",
    5: "Metano",
}


# ── DOWNLOAD E PARSING ─────────────────────────────────────────────────────────
def fetch_regional_data() -> pd.DataFrame:
    log.info(f"Download CSV regionale MIMIT: {MIMIT_URL}")
    r = requests.get(MIMIT_URL, timeout=TIMEOUT)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    r = requests.get(MIMIT_URL, timeout=60, headers=headers)

    from io import StringIO
    # Prova prima con punto e virgola, poi con virgola
    for sep in [";", ","]:
        df = pd.read_csv(
            StringIO(r.text),
            sep=sep,
            encoding=ENCODING,
            dtype=str,
            on_bad_lines="warn",
        )
        if len(df.columns) > 2:
            break

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    log.info(f"  → {len(df):,} righe, colonne: {list(df.columns)}")
    log.info(df.head(10).to_string())
    return df


def build_map_data(df: pd.DataFrame) -> pd.DataFrame:
    fuel_name    = FUEL_NAMES.get(FUEL_ID, "Benzina")
    self_label   = "SELF" if SELF_SERVICE == 1 else "SERVITO"

    # normalizza tutte le colonne stringa
    for col in df.columns:
        df[col] = df[col].str.strip()

    # individua colonne: regione, tipologia, erogazione, prezzo
    # i nomi esatti dipendono dal CSV — li cerchiamo in modo flessibile
    col_regione    = next((c for c in df.columns if "regione" in c or "region" in c), None)
    col_tipologia  = next((c for c in df.columns if "tipologia" in c or "tipo" in c or "carburante" in c), None)
    col_erogazione = next((c for c in df.columns if "erogazione" in c or "modalit" in c or "self" in c), None)
    col_prezzo     = next((c for c in df.columns if "prezzo" in c or "media" in c or "valore" in c), None)

    log.info(f"Colonne identificate: regione={col_regione}, tipologia={col_tipologia}, erogazione={col_erogazione}, prezzo={col_prezzo}")

    if not all([col_regione, col_tipologia, col_erogazione, col_prezzo]):
        log.error(f"Colonne non trovate. Colonne disponibili: {list(df.columns)}")
        sys.exit(1)

    # filtro
    mask = (
        df[col_tipologia].str.upper() == fuel_name.upper()
    ) & (
        df[col_erogazione].str.upper() == self_label
    )
    df_filt = df.loc[mask].copy()
    log.info(f"Righe filtrate ({fuel_name} {self_label}): {len(df_filt)}")

    if df_filt.empty:
        log.error("Nessuna riga dopo il filtro.")
        log.error(f"Valori unici tipologia: {df[col_tipologia].unique()}")
        log.error(f"Valori unici erogazione: {df[col_erogazione].unique()}")
        sys.exit(1)

    df_filt = df_filt.rename(columns={
        col_regione: "regione",
        col_prezzo:  "media_prezzo_raw",
    })

    # converti prezzo (può usare virgola come decimale)
    df_filt["media_prezzo"] = (
        df_filt["media_prezzo_raw"]
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    df_filt = df_filt.dropna(subset=["media_prezzo"])
    df_filt["media_prezzo"] = df_filt["media_prezzo"].round(3)
    df_filt["media_prezzo_str"] = df_filt["media_prezzo"].apply(lambda x: f"{x:.3f}".replace(".", ","))

    result = df_filt[["regione", "media_prezzo", "media_prezzo_str"]].copy()
    result = result.sort_values("regione").reset_index(drop=True)

    log.info(f"Regioni elaborate: {len(result)}")
    log.info(result.to_string(index=False))
    return result


# ── DATAWRAPPER API ────────────────────────────────────────────────────────────
def dw_headers() -> dict:
    return {"Authorization": f"Bearer {DW_API_KEY}", "Content-Type": "text/csv"}


def upload_data(chart_id: str, csv_text: str) -> None:
    url = f"{DW_BASE}/charts/{chart_id}/data"
    r = requests.put(url, headers=dw_headers(), data=csv_text.encode("utf-8"), timeout=TIMEOUT)
    r.raise_for_status()
    log.info(f"Dati caricati su Datawrapper chart {chart_id}")


def update_metadata(chart_id: str, fuel_label: str, ref_date: str) -> None:
    headers = {
        "Authorization": f"Bearer {DW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "metadata": {
            "annotate": {
                "notes": (
                    f"Media regionale prezzi {fuel_label} self service "
                    f"alle ore 8 del {ref_date}. "
                    f"Fonte: MIMIT – Osservatorio prezzi carburanti."
                )
            }
        }
    }
    url = f"{DW_BASE}/charts/{chart_id}"
    r = requests.patch(url, headers=headers, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    log.info("Metadati aggiornati")


def publish_chart(chart_id: str) -> None:
    url = f"{DW_BASE}/charts/{chart_id}/publish"
    r = requests.post(url, headers={"Authorization": f"Bearer {DW_API_KEY}"}, timeout=TIMEOUT)
    r.raise_for_status()
    log.info(f"Mappa pubblicata: https://datawrapper.dwcdn.net/{chart_id}/")


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    log.info("=== START update_map_regioni.py ===")
    ref_date   = datetime.now().strftime("%d/%m/%Y")
    fuel_label = FUEL_LABELS.get(FUEL_ID, f"tipo {FUEL_ID}")

    df  = fetch_regional_data()
    agg = build_map_data(df)

    csv_out = agg[["regione", "media_prezzo", "media_prezzo_str"]].to_csv(index=False)

    upload_data(DW_CHART_ID, csv_out)
    update_metadata(DW_CHART_ID, fuel_label, ref_date)
    publish_chart(DW_CHART_ID)

    log.info("=== DONE ===")


if __name__ == "__main__":
    main()
