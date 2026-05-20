"""
update_map.py
Scarica prezzi_alle_8 e anagrafica_impianti_attivi dal MIMIT,
calcola la media provinciale del carburante scelto (default: benzina self)
e aggiorna una mappa Datawrapper via API.

Separatore MIMIT: pipe "|" (dal 10 febbraio 2026)
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
PREZZI_URL     = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
ANAGRAFICA_URL = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
SEP            = "|"          # separatore MIMIT dal 10/02/2026
ENCODING       = "latin-1"   # encoding tipico dei CSV MIMIT

# ID carburante da monitorare (colonna "id_carburante" nel file prezzi)
# 1=Benzina, 2=Gasolio, 3=GPL, 5=Metano, 6=HVO — vedi metadati MIMIT
FUEL_ID = int(os.environ.get("FUEL_ID", "1"))

# self (1) o servito (0) — filtra il campo "self_service"
SELF_SERVICE = int(os.environ.get("SELF_SERVICE", "1"))

# Datawrapper
DW_API_KEY  = os.environ["DW_API_KEY"]          # secret GitHub
DW_CHART_ID = os.environ["DW_CHART_ID"]         # es. "AbCd1"
DW_BASE     = "https://api.datawrapper.de/v3"

TIMEOUT = 30  # secondi per le richieste HTTP

FUEL_LABELS = {
    1: "Benzina",
    2: "Gasolio",
    3: "GPL",
    5: "Metano",
    6: "HVO diesel",
}


# ── DOWNLOAD ───────────────────────────────────────────────────────────────────
def download_csv(url: str, name: str) -> pd.DataFrame:
    log.info(f"Download {name}: {url}")
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    from io import StringIO
    df = pd.read_csv(
        StringIO(r.text),
        sep=SEP,
        encoding=ENCODING,
        dtype=str,
        on_bad_lines="warn",
        skiprows=1,
    )
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    log.info(f"  → {len(df):,} righe, colonne: {list(df.columns)}")
    return df


# ── JOIN E AGGREGAZIONE ────────────────────────────────────────────────────────
def build_provincial_avg(prezzi: pd.DataFrame, anagrafica: pd.DataFrame) -> pd.DataFrame:
    """
    Join su id_impianto → filtra carburante e modalità → media per provincia.
    Restituisce DataFrame con colonne: provincia, media_prezzo, n_impianti
    """
    # normalizza chiave join
    prezzi["id_impianto"]     = prezzi["id_impianto"].str.strip()
    anagrafica["id_impianto"] = anagrafica["id_impianto"].str.strip()

    # cast numerici
    prezzi["id_carburante"] = pd.to_numeric(prezzi["id_carburante"], errors="coerce")
    prezzi["self_service"]  = pd.to_numeric(prezzi["self_service"],  errors="coerce")
    prezzi["prezzo"]        = pd.to_numeric(prezzi["prezzo"],        errors="coerce")

    # filtro carburante e modalità
    mask = (prezzi["id_carburante"] == FUEL_ID) & (prezzi["self_service"] == SELF_SERVICE)
    prezzi_filt = prezzi.loc[mask].copy()
    log.info(f"Prezzi filtrati (fuel={FUEL_ID}, self={SELF_SERVICE}): {len(prezzi_filt):,} righe")

    if prezzi_filt.empty:
        log.error("Nessun prezzo dopo il filtro. Controlla FUEL_ID e SELF_SERVICE.")
        sys.exit(1)

    # join con anagrafica
    merged = prezzi_filt.merge(anagrafica, on="id_impianto", how="left")

    # colonna provincia: MIMIT usa "provincia" o "prov" nell'anagrafica
    prov_col = next((c for c in merged.columns if "provincia" in c or c == "prov"), None)
    if prov_col is None:
        log.error(f"Colonna provincia non trovata. Colonne disponibili: {list(merged.columns)}")
        sys.exit(1)

    merged["provincia"] = merged[prov_col].str.strip().str.upper()

    # escludi province vuote o non riconosciute
    merged = merged.dropna(subset=["provincia", "prezzo"])
    merged = merged[merged["provincia"].str.len() == 2]  # sigla 2 lettere

    # aggregazione
    agg = (
        merged.groupby("provincia")
        .agg(
            media_prezzo=("prezzo", "mean"),
            n_impianti=("id_impianto", "nunique"),
        )
        .reset_index()
    )
    agg["media_prezzo"] = agg["media_prezzo"].round(3)
    agg = agg.sort_values("provincia")

    log.info(f"Province elaborate: {len(agg)}")
    log.info(agg.describe())
    return agg


# ── DATAWRAPPER API ────────────────────────────────────────────────────────────
def dw_headers() -> dict:
    return {"Authorization": f"Bearer {DW_API_KEY}", "Content-Type": "text/csv"}


def upload_data(chart_id: str, csv_text: str) -> None:
    url = f"{DW_BASE}/charts/{chart_id}/data"
    r = requests.put(url, headers=dw_headers(), data=csv_text.encode("utf-8"), timeout=TIMEOUT)
    r.raise_for_status()
    log.info(f"Dati caricati su Datawrapper chart {chart_id}")


def update_metadata(chart_id: str, fuel_label: str, ref_date: str) -> None:
    """Aggiorna titolo e nota con la data di riferimento."""
    headers = {
        "Authorization": f"Bearer {DW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "metadata": {
            "annotate": {
                "notes": (
                    f"Media provinciale prezzi {fuel_label} self service "
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
    log.info("=== START update_map.py ===")
    ref_date = datetime.utcnow().strftime("%d/%m/%Y")
    fuel_label = FUEL_LABELS.get(FUEL_ID, f"tipo {FUEL_ID}")

    prezzi     = download_csv(PREZZI_URL,     "prezzi_alle_8")
    anagrafica = download_csv(ANAGRAFICA_URL, "anagrafica_impianti")

    agg = build_provincial_avg(prezzi, anagrafica)

    # CSV per Datawrapper: colonne provincia (sigla) + media_prezzo
    # Datawrapper mappa Italia per provincia usa le sigle ISTAT a 2 lettere
    csv_out = agg[["provincia", "media_prezzo", "n_impianti"]].to_csv(index=False)
    log.info(f"Preview output:\n{agg.head(10).to_string(index=False)}")

    upload_data(DW_CHART_ID, csv_out)
    update_metadata(DW_CHART_ID, fuel_label, ref_date)
    publish_chart(DW_CHART_ID)

    log.info("=== DONE ===")


if __name__ == "__main__":
    main()
