#!/usr/bin/env python3
"""
ESTRAI TURNI - ACTV Extraurbano Sud
Legge i PDF cartellini (Lun-Ven, Sabato, Festivo) e produce il file `turni.json`
che viene caricato dalla pagina web `index.html`.

Ogni turno viene ricondotto al proprio deposito in base al numero:
0xx=Dolo, 1xx=Cavarzere, 2xx=Bojon, 3xx=Padova (PD Parch), 5xx=Fossò.
I 9xx sono turni brevi "jolly" e restano fuori dalla turnazione.

Uso:
    python estrai_turni.py                        # cerca i PDF in Download
    python estrai_turni.py percorso1.pdf percorso2.pdf ...
    python estrai_turni.py -o mio_file.json       # cambia file di uscita

Dipendenza:  python -m pip install pypdf
"""
import argparse
import glob
import io
import json
import os
import re
import sys
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from pypdf import PdfReader
except ImportError:
    print("MANCA pypdf:  python -m pip install pypdf")
    sys.exit(1)

# ---------------------------------------------------------------- parsing PDF

RE_HDR = re.compile(r"^D(\d{3})\s*(.*)$")
RE_ORA = re.compile(r"^Orario\s+(-?\d+,\d+)\s+(-?\d+,\d{2})(.*)$")
RE_TIME = re.compile(r"(\d{1,2}):(\d{2})")
RE_DATA = re.compile(r"Validit.{0,12}?Data:\s*(\d{2}/\d{2}/\d{4})")
RE_MONTA = re.compile(r"^Monta\s+(.*?)\s*Smonta\s*(.*)$")


def leggi_pdf(path):
    """Ritorna la lista dei cartellini contenuti nel PDF."""
    testo = []
    for pagina in PdfReader(path).pages:
        testo.append(pagina.extract_text() or "")

    turni, corrente = [], None
    for riga in "\n".join(testo).splitlines():
        m = RE_HDR.match(riga)
        if m:
            if corrente:
                turni.append(corrente)
            corrente = {"numero": int(m.group(1)), "tipo": m.group(2).strip()}
            continue
        if corrente is None:
            continue
        mo = RE_ORA.match(riga)
        if mo:
            ore = float(mo.group(1).replace(",", "."))
            tratti = [
                int(h) * 60 + int(mm) for h, mm in RE_TIME.findall(mo.group(3))
            ]
            corrente["ore"] = ore
            corrente["minuti"] = tratti
            continue
        md = RE_DATA.search(riga)
        if md and "data" not in corrente:
            corrente["data"] = md.group(1)
        mm_ = RE_MONTA.match(riga)
        if mm_ and "monta" not in corrente:
            corrente["monta"] = mm_.group(1).strip()
    if corrente:
        turni.append(corrente)
    return turni


def unisci(turni):
    """Unifica i cartellini duplicati dello stesso numero (tenendo quelli con orario)."""
    out = {}
    for t in turni:
        n = t["numero"]
        if n not in out:
            out[n] = t
        elif "minuti" in t and "minuti" not in out[n]:
            out[n] = t
    return out


# ------------------------------------------------------- classificazione turni

def coppie(minuti):
    return [
        (minuti[i], minuti[i + 1]) for i in range(0, len(minuti) - 1, 2)
    ]


def hm(m):
    m %= 24 * 60
    return f"{m // 60:02d}:{m % 60:02d}"


def classifica(t, p):
    """t = cartellino, p = soglie (dict). Ritonna codice categoria."""
    minuti = t.get("minuti") or []
    if len(minuti) < 2:
        return None
    tr = coppie(minuti)
    if len(tr) == 2:
        return "SPEZZATO"
    if len(tr) != 1:
        return None
    inizio, fine = tr[0]
    if fine < inizio:
        fine += 24 * 60
    if t.get("ore", 99) < p["ore_ridotto"]:
        return "RIDOTTO"
    if inizio < p["fine_primo"] and fine <= p["max_primo"]:
        return "PRIMO"
    if inizio >= p["inizio_terzo"] or fine > p["fine_terzo"]:
        return "TERZO"
    return "SECONDO"


# --------------------------------------------------------------- depositi
# Il numero del turno indica il deposito di appartenenza (verificato sui
# cartellini dalla riga "Monta ..."):  0xx=Dolo 1xx=Cavarzere 2xx=Bojon
# 3xx=Padova (PD Parch) 5xx=Fossò.  I 9xx sono turni brevi "jolly" che
# l'ufficio turni assegna a mano, quindi NON entrano nella turnazione.
DEPOSITI = {
    0: ("dolo",      "Dolo",             "DEP.DOLO / DOLO.DEP"),
    1: ("cavarzere", "Cavarzere",        "DEP.CAV"),
    2: ("bojon",     "Bojon",            "BOJON PK"),
    3: ("padova",    "Padova",          "PD PARCH"),   # nei cartellini e' scritto "PD PARCH"
    5: ("fosso",     "Fossò",            "FOSSO'PK / FOS PK B"),
}

# --------------------------------------------------------------- fasce numeriche

def intervalli(numeri):
    """Raggruppa i numeri in fasce continue (es. 1-54, 101-130, 301-311...)."""
    if not numeri:
        return []
    gruppi = {}
    for n in numeri:
        gruppi.setdefault(n // 100, []).append(n)
    fasce = []
    for _, ns in sorted(gruppi.items()):
        ns = sorted(ns)
        start = prev = ns[0]
        for n in ns[1:]:
            if n - prev > 10:          # stacco netto -> nuova fascia
                fasce.append((start, prev))
                start = n
            prev = n
        fasce.append((start, prev))
    return fasce


# ----------------------------------------------------------------------- main

SOGLIE = {
    "ore_ridotto": 4.0,     # turni piu' breghi di questo -> RIDOTTO
    "fine_primo": 11 * 60,  # un PRIMO deve cominciare prima delle 11:00
    "max_primo": 14 * 60,   # ... e finire entro le 14:00
    "inizio_terzo": 14 * 60,  # un TERZO comincia dalle 14:00...
    "fine_terzo": 21 * 60,    # ... oppure finisce dopo le 21:00
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="*", help="PDF cartellini (default: Download)")
    ap.add_argument("-o", "--out", default=None, help="file turni.json")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(here, "turni.json")

    pdfs = args.pdf
    if not pdfs:
        dl = os.path.join(os.path.expanduser("~"), "Downloads")
        pdfs = sorted(glob.glob(os.path.join(dl, "*TURNI*.pdf")))
    if not pdfs:
        print("Nessun PDF trovato.")
        sys.exit(1)

    set_trovati = {}
    for p in pdfs:
        nome = os.path.basename(p).upper()
        if "SABATO" in nome:
            chiave = "sabato"
        elif "FESTIVO" in nome:
            chiave = "festivo"
        else:
            chiave = "lunven"
        print(f"[{chiave:<7}] {os.path.basename(p)}")
        set_trovati[chiave] = unisci(leggi_pdf(p))

    lunven = set_trovati.get("lunven", {})
    sabato = set_trovati.get("sabato", {})
    festivo = set_trovati.get("festivo", {})

    tutti = sorted(set(lunven) | set(sabato) | set(festivo))

    turni, jolly = [], []
    for n in tutti:
        lv, sb, fs = lunven.get(n), sabato.get(n), festivo.get(n)
        # la categoria viene dal Lun-Ven; in sua assenza da Sabato/Festivo
        base, origine = None, None
        for src, etichetta in ((lv, "lunven"), (sb, "sabato"), (fs, "festivo")):
            if src and classifica(src, SOGLIE):
                base, origine = classifica(src, SOGLIE), etichetta
                break
        voce = {
            "n": n,
            "cat": base or "DISP",
            "origine": origine,
            "ore": (lv or sb or fs or {}).get("ore"),
            "monta": (lv or sb or fs or {}).get("monta"),
        }
        for chiave, src in (("lv", lv), ("sb", sb), ("fs", fs)):
            if src and "minuti" in src:
                tr = coppie(src["minuti"])
                voce[chiave] = {
                    "ore": src.get("ore"),
                    "tratti": [
                        [
                            hm(a),
                            hm(b + (24 * 60) if b < a else b),
                        ]
                        for a, b in tr
                    ],
                }
            else:
                voce[chiave] = None

        # jolly: turni brevi o numeri fuori dalle fasce dei depositi
        gruppo = n // 100
        breve = voce["ore"] is not None and voce["ore"] < SOGLIE["ore_ridotto"]
        if breve or gruppo not in DEPOSITI:
            voce["cat"] = "RIDOTTO"
            jolly.append(voce)
            continue

        voce["deposito"] = DEPOSITI[gruppo][0]
        if origine and origine != "lunven":
            voce["nota"] = f"nessun turno lun-ven: da {origine}"
        turni.append(voce)

    # ogni deposito ha la sua numerazione, le sue fasce e le sue settimane
    # "disponibile": la turnazione gira dentro il deposito
    depositi = []
    for gruppo, (cod, nome, sigla) in DEPOSITI.items():
        propri = [t for t in turni if t["deposito"] == cod]
        if not propri:
            continue
        ns = sorted(t["n"] for t in propri)
        fasce = intervalli(ns)
        occupati = set(ns)
        disp = [n for a, b in fasce for n in range(a, b + 1) if n not in occupati]
        depositi.append({
            "codice": cod,
            "nome": nome,
            "sigla": sigla,
            "fasce": fasce,
            "disponibili": disp,
            "turni": propri,
        })

    print()
    for d in depositi:
        conteggi = {}
        for t in d["turni"]:
            conteggi[t["cat"]] = conteggi.get(t["cat"], 0) + 1
        print(f"{d['nome']:<18} {len(d['turni']):>3} turni  "
              f"posizioni {sum(b-a+1 for a, b in d['fasce']):>3}  "
              f"disponibili {len(d['disponibili']):>2}  {json.dumps(conteggi, ensure_ascii=False)}")
    print(f"{'JOLLY (no turnazione)':<18} {len(jolly):>3} turni  "
          f"{[t['n'] for t in jolly]}")

    dati = {
        "generato": date.today().isoformat(),
        "soglie": SOGLIE,
        "sorgenti": [os.path.basename(p) for p in pdfs],
        "depositi": depositi,
        "jolly": jolly,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
    print("\nscritto:", out)

    # aggiorna i dati incollati dentro index.html (cosi' la pagina resta autonoma)
    html = os.path.join(here, "index.html")
    if os.path.exists(html):
        src = open(html, encoding="utf-8").read()
        inizio, fine = "/*==DATI_INIZIO==*/", "/*==DATI_FINE==*/"
        if inizio in src and fine in src:
            testo = json.dumps(dati, ensure_ascii=False, indent=1)
            testa, resto = src.split(inizio, 1)       # solo il primo marcatore
            _, coda = resto.split(fine, 1)            # fino al primo marcatore di fine
            src = testa + inizio + "\n" + testo + "\n" + fine + coda
            open(html, "w", encoding="utf-8").write(src)
            print("aggiornati i dati dentro index.html")


if __name__ == "__main__":
    main()
