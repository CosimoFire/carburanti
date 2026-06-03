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
SEP            = "|"
ENCODING       = "latin-1"

FUEL_ID      = int(os.environ.get("FUEL_ID", "1"))
SELF_SERVICE = int(os.environ.get("SELF_SERVICE", "1"))

DW_API_KEY  = os.environ["DW_API_KEY"]
DW_CHART_ID = os.environ["DW_CHART_ID"]
DW_BASE     = "https://api.datawrapper.de/v3"

TIMEOUT = 30

FUEL_LABELS = {
    1: "Benzina",
    2: "Gasolio",
    3: "GPL",
    5: "Metano",
    6: "HVO diesel",
}

# ── NOMI PROVINCE ──────────────────────────────────────────────────────────────
PROVINCE_NOMI = {
    "AG": "Agrigento", "AL": "Alessandria", "AN": "Ancona", "AO": "Aosta",
    "AP": "Ascoli Piceno", "AQ": "L'Aquila", "AR": "Arezzo", "AT": "Asti",
    "AV": "Avellino", "BA": "Bari", "BG": "Bergamo", "BI": "Biella",
    "BL": "Belluno", "BN": "Benevento", "BO": "Bologna", "BR": "Brindisi",
    "BS": "Brescia", "BT": "Barletta-Andria-Trani", "BZ": "Bolzano",
    "CA": "Cagliari", "CB": "Campobasso", "CE": "Caserta", "CH": "Chieti",
    "CL": "Caltanissetta", "CN": "Cuneo", "CO": "Como", "CR": "Cremona",
    "CS": "Cosenza", "CT": "Catania", "CZ": "Catanzaro", "EN": "Enna",
    "FC": "Forlì-Cesena", "FE": "Ferrara", "FG": "Foggia", "FI": "Firenze",
    "FM": "Fermo", "FR": "Frosinone", "GE": "Genova", "GO": "Gorizia",
    "GR": "Grosseto", "IM": "Imperia", "IS": "Isernia", "KR": "Crotone",
    "LC": "Lecco", "LE": "Lecce", "LI": "Livorno", "LO": "Lodi",
    "LT": "Latina", "LU": "Lucca", "MB": "Monza e Brianza", "MC": "Macerata",
    "ME": "Messina", "MI": "Milano", "MN": "Mantova", "MO": "Modena",
    "MS": "Massa-Carrara", "MT": "Matera", "NA": "Napoli", "NO": "Novara",
    "NU": "Nuoro", "OR": "Oristano", "PA": "Palermo", "PC": "Piacenza",
    "PD": "Padova", "PE": "Pescara", "PG": "Perugia", "PI": "Pisa",
    "PN": "Pordenone", "PO": "Prato", "PR": "Parma", "PT": "Pistoia",
    "PU": "Pesaro e Urbino", "PV": "Pavia", "PZ": "Potenza", "RA": "Ravenna",
    "RC": "Reggio Calabria", "RE": "Reggio Emilia", "RG": "Ragusa",
    "RI": "Rieti", "RM": "Roma", "RN": "Rimini", "RO": "Rovigo",
    "SA": "Salerno", "SI": "Siena", "SO": "Sondrio", "SP": "La Spezia",
    "SR": "Siracusa", "SS": "Sassari", "SU": "Sud Sardegna", "SV": "Savona",
    "TA": "Taranto", "TE": "Teramo", "TN": "Trento", "TO": "Torino",
    "TP": "Trapani", "TR": "Terni", "TS": "Trieste", "TV": "Treviso",
    "UD": "Udine", "VA": "Varese", "VB": "Verbano-Cusio-Ossola",
    "VC": "Vercelli", "VE": "Venezia", "VI": "Vicenza", "VR": "Verona",
    "VT": "Viterbo", "VV": "Vibo Valentia",
}

# ── REGIONI ────────────────────────────────────────────────────────────────────
PROVINCE_REGIONI = {
    "AG": "Sicilia", "AL": "Piemonte", "AN": "Marche", "AO": "Valle d'Aosta",
    "AP": "Marche", "AQ": "Abruzzo", "AR": "Toscana", "AT": "Piemonte",
    "AV": "Campania", "BA": "Puglia", "BG": "Lombardia", "BI": "Piemonte",
    "BL": "Veneto", "BN": "Campania", "BO": "Emilia-Romagna", "BR": "Puglia",
    "BS": "Lombardia", "BT": "Puglia", "BZ": "Trentino-Alto Adige",
    "CA": "Sardegna", "CB": "Molise", "CE": "Campania", "CH": "Abruzzo",
    "CL": "Sicilia", "CN": "Piemonte", "CO": "Lombardia", "CR": "Lombardia",
    "CS": "Calabria", "CT": "Sicilia", "CZ": "Calabria", "EN": "Sicilia",
    "FC": "Emilia-Romagna", "FE": "Emilia-Romagna", "FG": "Puglia",
    "FI": "Toscana", "FM": "Marche", "FR": "Lazio", "GE": "Liguria",
    "GO": "Friuli-Venezia Giulia", "GR": "Toscana", "IM": "Liguria",
    "IS": "Molise", "KR": "Calabria", "LC": "Lombardia", "LE": "Puglia",
    "LI": "Toscana", "LO": "Lombardia", "LT": "Lazio", "LU": "Toscana",
    "MB": "Lombardia", "MC": "Marche", "ME": "Sicilia", "MI": "Lombardia",
    "MN": "Lombardia", "MO": "Emilia-Romagna", "MS": "Toscana",
    "MT": "Basilicata", "NA": "Campania", "NO": "Piemonte", "NU": "Sardegna",
    "OR": "Sardegna", "PA": "Sicilia", "PC": "Emilia-Romagna", "PD": "Veneto",
    "PE": "Abruzzo", "PG": "Umbria", "PI": "Toscana", "PN": "Friuli-Venezia Giulia",
    "PO": "Toscana", "PR": "Emilia-Romagna", "PT": "Toscana",
    "PU": "Marche", "PV": "Lombardia", "PZ": "Basilicata", "RA": "Emilia-Romagna",
    "RC": "Calabria", "RE": "Emilia-Romagna", "RG": "Sicilia", "RI": "Lazio",
    "RM": "Lazio", "RN": "Emilia-Romagna", "RO": "Veneto", "SA": "Campania",
    "SI": "Toscana", "SO": "Lombardia", "SP": "Liguria", "SR": "Sicilia",
    "SS": "Sardegna", "SU": "Sardegna", "SV": "Liguria", "TA": "Puglia",
    "TE": "Abruzzo", "TN": "Trentino-Alto Adige", "TO": "Piemonte",
    "TP": "Sicilia", "TR": "Umbria", "TS": "Friuli-Venezia Giulia",
    "TV": "Veneto", "UD": "Friuli-Venezia Giulia", "VA": "Lombardia",
    "VB": "Piemonte", "VC": "Piemonte", "VE": "Veneto", "VI": "Veneto",
    "VR": "Veneto", "VT": "Lazio", "VV": "Calabria",
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
        keep_default_na=False,
        na_values=[""],
    )
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    log.info(f"  → {len(df):,} righe, colonne: {list(df.columns)}")
    return df


# ── JOIN E AGGREGAZIONE ────────────────────────────────────────────────────────
def build_provincial_avg(prezzi: pd.DataFrame, anagrafica: pd.DataFrame) -> pd.DataFrame:
    prezzi     = prezzi.rename(columns={"idimpianto": "id_impianto"})
    anagrafica = anagrafica.rename(columns={"idimpianto": "id_impianto"})

    prezzi["id_impianto"]     = prezzi["id_impianto"].str.strip()
    anagrafica["id_impianto"] = anagrafica["id_impianto"].str.strip()

    prezzi["isself"] = pd.to_numeric(prezzi["isself"], errors="coerce")
    prezzi["prezzo"] = pd.to_numeric(prezzi["prezzo"], errors="coerce")

    FUEL_NAMES = {
        1: "Benzina",
        2: "Gasolio",
        3: "GPL",
        5: "Metano",
        6: "HVO diesel",
    }
    fuel_name = FUEL_NAMES.get(FUEL_ID, "Benzina")
    mask = (
        prezzi["desccarburante"].str.strip().str.lower() == fuel_name.lower()
    ) & (prezzi["isself"] == SELF_SERVICE)
    prezzi_filt = prezzi.loc[mask].copy()
    log.info(f"Prezzi filtrati (fuel={fuel_name}, self={SELF_SERVICE}): {len(prezzi_filt):,} righe")

    if prezzi_filt.empty:
        log.error("Nessun prezzo dopo il filtro. Controlla FUEL_ID e SELF_SERVICE.")
        sys.exit(1)

    merged = prezzi_filt.merge(anagrafica[["id_impianto", "provincia"]], on="id_impianto", how="left")

    merged["provincia"] = merged["provincia"].str.strip().str.upper()
    merged = merged.dropna(subset=["provincia", "prezzo"])
    merged = merged[merged["provincia"].str.len() == 2]

    agg = (
        merged.groupby("provincia")
        .agg(
            media_prezzo=("prezzo", "mean"),
            n_impianti=("id_impianto", "nunique"),
        )
        .reset_index()
    )
    agg["media_prezzo"] = agg["media_prezzo"].round(3)
    agg["media_prezzo_str"] = agg["media_prezzo"].apply(lambda x: f"{x:.3f}".replace(".", ","))
    agg["nome_provincia"] = agg["provincia"].map(PROVINCE_NOMI)
    agg["regione"] = agg["provincia"].map(PROVINCE_REGIONI)
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
    ref_date = datetime.now().strftime("%d/%m/%Y")
    fuel_label = FUEL_LABELS.get(FUEL_ID, f"tipo {FUEL_ID}")

    prezzi     = download_csv(PREZZI_URL,     "prezzi_alle_8")
    anagrafica = download_csv(ANAGRAFICA_URL, "anagrafica_impianti")

    agg = build_provincial_avg(prezzi, anagrafica)

    csv_out = agg[["provincia", "nome_provincia", "regione", "media_prezzo", "media_prezzo_str", "n_impianti"]].to_csv(index=False)
    log.info(f"Preview output:\n{agg.head(10).to_string(index=False)}")

    upload_data(DW_CHART_ID, csv_out)
    update_metadata(DW_CHART_ID, fuel_label, ref_date)
    publish_chart(DW_CHART_ID)

    log.info("=== DONE ===")


if __name__ == "__main__":
    main()
