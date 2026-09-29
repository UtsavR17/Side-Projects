"""MTC (Mauritius Turf Club) specific parsers for human-saved pages and exports.

Two official shapes are supported — both obtained by a person viewing/downloading
the page, which is the compliant route since the site's robots.txt denies bots:

1. **Race page HTML** (`table.race-card-mtc`) — full result/form table with
   FP, horse (plus its MTC horse-id link), trainer, jockey, equipment, HWT
   (body weight + delta), barrier, weight, margin, SP, Win/Place dividends,
   time and official rating; plus the tote dividend and sectional-time tables.

2. **Result PDF** ("Race-Result-<meeting>-R<n>.pdf") — the official per-race
   download. Its text extracts in clean columns, so we slice by the header
   offsets. Trainer and jockey come out on separate lines there.

Both return the same dict shape so one ingest path can consume them.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

NUM = re.compile(r"-?\d+(?:\.\d+)?")
SADDLE_PREFIX = re.compile(r"^\s*\d+\.\s*")
HORSE_LINK = re.compile(r"/horse/([a-z0-9\-]+)/(\d+)", re.I)
MEETING_LINE = re.compile(r"Meeting\s+(\d+)", re.I)
RACE_LINE = re.compile(
    r"Race\s+(\d+)\s*-\s*(\d{1,2}:\d{2})\s*-\s*(.*?)\s*-\s*\[([^\]]+)\]\s*-\s*(\d+)\s*m",
    re.I,
)


def _num(text: str | None) -> float | None:
    if not text:
        return None
    match = NUM.search(str(text).replace(",", ""))
    return float(match.group(0)) if match else None


def _int(text: str | None) -> int | None:
    value = _num(text)
    return int(value) if value is not None else None


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def parse_hwt(cell_text: str) -> tuple[float | None, float | None]:
    """'503 (+17)' -> (503.0, 17.0); '465' -> (465.0, None)."""
    text = _clean(cell_text)
    total = _num(text)
    delta = None
    m = re.search(r"\(\s*([+-]?\d+(?:\.\d+)?)\s*\)", text)
    if m:
        delta = float(m.group(1))
    return total, delta


def looks_like_mtc_page(text: str) -> bool:
    return "race-card-mtc" in text or (
        "MTC Jockey Club" in text and "Mauritius Turf Club" in text
    )


def _split_trainer_jockey(cell) -> tuple[str | None, str | None, float | None]:
    """Trainer is the first span, jockey the second; the jockey may carry a claim."""
    if cell is None:
        return None, None, None
    spans = []
    for span in cell.find_all("span"):
        text = _clean(span.get_text(" "))
        if not text or "HWT" in text or "Last Run" in text or "Current" in text:
            continue
        spans.append(text)
    trainer = spans[0] if spans else None
    jockey_raw = spans[1] if len(spans) > 1 else None
    claim = None
    jockey = jockey_raw
    if jockey_raw:
        m = re.search(r"\(\s*(-?\d+(?:\.\d+)?)\s*kg\s*\)", jockey_raw, re.I)
        if m:
            claim = abs(float(m.group(1)))
            jockey = _clean(jockey_raw[: m.start()] + jockey_raw[m.end():])
    return trainer, jockey, claim


def _race_no_from_soup(soup: BeautifulSoup, html: str) -> int | None:
    for pattern in (r'data-tab-no="(\d+)"', r"Race\s+(\d+)\s*-", r"Race\s+(\d+)\b"):
        m = re.search(pattern, html)
        if m:
            value = int(m.group(1))
            if 1 <= value <= 15:
                return value
    return None


def _fix_dash_mojibake(text: str) -> str:
    """Saved pages sometimes carry a mis-decoded en/em dash as 'û' or 'Û'."""
    text = re.sub(r"\s+[ûÛ]\s+", " - ", text)
    text = text.replace("â€™", "'").replace("Â", "")
    return text


def _race_name_from_html(html: str) -> str | None:
    """Prefer an explicit 'Race N - HH:MM - Name' header, else the page title."""
    explicit = re.search(r"Race\s+\d+\s*-\s*\d{1,2}:\d{2}\s*-\s*([^<\[\]]{3,90})", html)
    if explicit:
        name = _clean(explicit.group(1)).strip(" -")
        if name:
            return _fix_dash_mojibake(name)
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if not title:
        return None
    parts = [p.strip() for p in title.group(1).split("|")]
    for index, part in enumerate(parts):
        if re.match(r"Meeting\s+\d+", part, re.I) and index + 2 < len(parts):
            return _fix_dash_mojibake(parts[index + 2].strip()) or None
    return None


def _prize_from_text(flat: str) -> str | None:
    m = re.search(r"(Rs\s?[\d,]+)", flat)
    return m.group(1) if m else None


def _parse_dividends(soup: BeautifulSoup) -> dict:
    """Tote dividends table: Pool | Horse/combination | Dividend."""
    for table in soup.find_all("table"):
        header = _clean(table.get_text(" ")).lower()
        if "dividend" not in header:
            continue
        out: dict[str, dict] = {}
        for row in table.find_all("tr"):
            cells = [_clean(c.get_text(" ")) for c in row.find_all(["td", "th"])]
            if len(cells) < 3 or cells[0].lower().startswith("pool"):
                continue
            pool, selection, amount = cells[0], cells[1], _num(cells[2])
            if pool and amount is not None:
                out.setdefault(pool, {})[selection or "-"] = amount
        if out:
            return out
    return {}


def _parse_sectionals(flat: str) -> dict:
    m = re.search(
        r"Sectional Times?\s*((?:\d{3,4}m\s*)+)((?:\d+:\d+(?:\.\d+)?\s*)+)", flat, re.I
    )
    if not m:
        return {}
    marks = re.findall(r"(\d{3,4})m", m.group(1))
    times = re.findall(r"(\d+:\d+(?:\.\d+)?)", m.group(2))
    return _zip_sectionals(marks, times)


def _zip_sectionals(marks: list[str], times: list[str]) -> dict:
    from pipeline.parsing import parse_time

    out: dict = {}
    for mark, time_text in zip(marks, times):
        value = parse_time(time_text)
        if value is not None:
            out[f"{mark}m"] = round(value, 2)
    return out


def _parse_sectionals_from_soup(soup: BeautifulSoup) -> dict:
    """MTC renders sectionals as a 2-row table: marks on top, times below."""
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        first = [_clean(c.get_text(" ")) for c in rows[0].find_all(["td", "th"])]
        second = [_clean(c.get_text(" ")) for c in rows[1].find_all(["td", "th"])]
        marks = [re.match(r"^(\d{3,4})\s*m$", cell) for cell in first if cell]
        if not marks or not all(marks):
            continue
        mark_values = [m.group(1) for m in marks]
        times = re.findall(r"\d+:\d+(?:\.\d+)?", " ".join(second))
        if times:
            parsed = _zip_sectionals(mark_values, times)
            if parsed:
                return parsed
    return {}


HEADER_KEYS = (
    ("fp", ("fp",)),
    ("horse", ("horse",)),
    ("people", ("trainer", "jockey")),
    ("gear", ("equip",)),
    ("hwt", ("hwt",)),
    ("bp", ("bp",)),
    ("weight", ("weight",)),
    ("margin", ("margin",)),
    ("sp", ("sp",)),
    ("win", ("win",)),
    ("place", ("place",)),
    ("time", ("time",)),
    ("rating", ("rating",)),
)


PDF_HEADER_TOKENS = (
    ("fp", "FP"), ("horse", "Horse"), ("people", "Trainer"), ("gear", "Equip"),
    ("hwt", "HWT"), ("bp", "BP"), ("weight", "Weight"), ("margin", "Margin"),
    ("sp", "SP"), ("win", "Win"), ("place", "Place"), ("time", "Time"),
    ("rating", "Rating"),
)


def looks_like_mtc_result_pdf(text: str) -> bool:
    return "Results for Race Meeting" in text or (
        "MTC Jockey Club" in text and "FP" in text and "Rating" in text
    )


def pdf_text(data: bytes | str) -> str:
    """Extract text (layout mode) from PDF bytes, or pass text through."""
    if isinstance(data, str):
        return data
    if not data.lstrip().startswith(b"%PDF"):
        return data.decode("utf-8", errors="replace")
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text(extraction_mode="layout"))
            except TypeError:  # older pypdf signature
                pages.append(page.extract_text() or "")
        return "\n".join(pages)
    except ImportError:  # pypdf optional
        return ""
    except Exception:  # noqa: BLE001 — a corrupt PDF must not break the pipeline
        return ""


def _deglue(text: str) -> str:
    """Fix pypdf layout artefacts: 'T he  Great  Gusto' -> 'The Great Gusto'."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"([A-Z])\s+([a-z])", r"\1\2", text)
    text = text.replace("û", "-").replace("–", "-")
    return _clean(text)


def _pdf_columns(header_line: str) -> list[tuple[str, int, int]]:
    positions = []
    for key, token in PDF_HEADER_TOKENS:
        index = header_line.find(token)
        if index >= 0:
            positions.append((key, index))
    positions.sort(key=lambda item: item[1])
    columns = []
    for i, (key, start) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else len(header_line) + 200
        columns.append((key, start, end))
    return columns


def parse_mtc_result_pdf(data: bytes | str, default_date=None) -> tuple[dict, list[str]]:
    """Parse the official 'Race-Result-*.pdf' export (one race per file)."""
    from pipeline.parsing import parse_date, parse_time

    text = pdf_text(data)
    if not text.strip():
        return {}, ["PDF text could not be extracted (is pypdf installed?)"]

    lines = text.splitlines()
    races: list[dict] = []
    warnings: list[str] = []
    meeting = None
    date = None
    columns: list[tuple[str, int, int]] = []
    runners: list[dict] = []
    sectionals: dict = {}

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if meeting is None:
            head = re.search(r"Meeting\s+(\d+)", line)
            if head:
                meeting = int(head.group(1))
            date_match = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", line)
            if date_match:
                date = parse_date(date_match.group(1))
        if "FP" in line and "Horse" in line and "Rating" in line:
            columns = _pdf_columns(line)
            continue
        if _clean(line) == "Jockey":
            continue
        if re.search(r"R\s*ace\s+\d+", line):
            races.append(_pdf_race_meta(line))
            continue
        if re.search(r"Sectional Times", line, re.I):
            continue

        if columns and re.match(r"^\s*\d+\s+\d+\.", line):
            runners.append(_pdf_runner(line, columns))
        elif columns and runners and _only_in_column(line, columns, "people"):
            # continuation line: the jockey sits under the trainer column
            value = _slice(line, columns, "people")
            if value and value.lower() != "jockey":
                jockey, claim = _strip_claim(value)
                runners[-1]["jockey"] = jockey
                if claim is not None:
                    runners[-1]["claim_kg"] = claim
        if re.search(r"(\d{3,4})m", line) and re.search(r"\d+:\d+\.\d+", line) and not runners:
            sectionals.update(_parse_sectionals(_clean(line)))

    if not runners:
        warnings.append("no runner rows recognised in the PDF")
    if not races:
        warnings.append("race header line not recognised in the PDF")

    meta = races[0] if races else {}
    parsed = {
        "source": "mtc-pdf",
        "meeting_no": meeting or meta.get("meeting_no"),
        "date": date or default_date,
        "race_no": meta.get("race_no"),
        "race_name": meta.get("race_name"),
        "distance_m": meta.get("distance_m"),
        "race_class": meta.get("race_class"),
        "prize": meta.get("prize"),
        "race_time_label": meta.get("race_time_label"),
        "win_time_s": meta.get("win_time_s"),
        "runners": runners,
        "tote_dividends": {},
        "sectional_times": sectionals,
        "warnings": warnings,
    }
    return parsed, warnings


def _slice(line: str, columns, key: str) -> str | None:
    for name, start, end in columns:
        if name == key:
            value = _clean(line[start:end])
            return value or None
    return None


def _only_in_column(line: str, columns, key: str) -> bool:
    """True when the line's only content sits inside the given column."""
    stripped = line.strip()
    if not stripped or re.match(r"^\d", stripped):
        return False
    for name, start, end in columns:
        if name == key:
            return bool(_clean(line[start:end])) and _clean(line[:start]) == "" and \
                _clean(line[end:]) == ""
    return False


def _strip_claim(value: str) -> tuple[str, float | None]:
    """'B ECROIGNARD(-4kg)' -> ('B ECROIGNARD', 4.0)."""
    text = _clean(value)
    m = re.search(r"\(\s*(-?\d+(?:\.\d+)?)\s*kg\s*\)", text, re.I)
    if not m:
        return text, None
    return _clean(text[: m.start()] + text[m.end():]), abs(float(m.group(1)))


def _pdf_race_meta(line: str) -> dict:
    """'R ace 1 - 12: 30 - The Great Gusto - [0-25] - 1400m - R s 188000 - WinTime: 1: 24.88'"""
    from pipeline.parsing import parse_time

    meta: dict = {}
    race = re.search(r"R\s*ace\s+(\d+)\s*-\s*(\d{1,2})\s*:\s*(\d{2})", line, re.I)
    if race:
        meta["race_no"] = int(race.group(1))
        meta["race_time_label"] = f"{int(race.group(2)):02d}:{race.group(3)}"

    win_time = re.search(r"Win\s*Time\s*:?\s*(\d+)\s*:\s*(\d+(?:\.\d+)?)", line, re.I)
    if win_time:
        meta["win_time_s"] = parse_time(f"{win_time.group(1)}:{win_time.group(2)}")

    klass = re.search(r"\[\s*([0-9]{1,3}\s*-\s*[0-9]{1,3})\s*\]", line)
    if klass:
        meta["race_class"] = klass.group(1).replace(" ", "")

    distance = re.search(r"(\d{3,4})\s*m\b", line)
    if distance:
        meta["distance_m"] = int(distance.group(1))

    prize = re.search(r"R\s*s\s*([\d,]+)", line)
    if prize:
        meta["prize"] = f"Rs {prize.group(1)}"

    # race name = text between the start time and the class bracket
    if race and klass and klass.start() > race.end():
        meta["race_name"] = _deglue(line[race.end():klass.start()].strip(" -"))
    return meta


def _pdf_runner(line: str, columns) -> dict:
    """One runner row, sliced by the header column offsets."""
    fp_text = _slice(line, columns, "fp") or ""
    horse_text = _slice(line, columns, "horse") or ""
    saddle_no = None
    prefix = re.match(r"\s*(\d+)\.", horse_text)
    if prefix:
        saddle_no = int(prefix.group(1))
    name = SADDLE_PREFIX.sub("", _deglue(horse_text)).strip()
    body_weight, body_delta = parse_hwt(_slice(line, columns, "hwt") or "")
    return {
        "finish_position": _int(fp_text),
        "saddle_no": saddle_no,
        "horse": name,
        "external_id": None,
        "trainer": _slice(line, columns, "people"),
        "jockey": None,          # arrives on the continuation line (Jockey row)
        "claim_kg": None,
        "gear": _slice(line, columns, "gear"),
        "body_weight_kg": body_weight,
        "body_weight_delta": body_delta,
        "barrier": _int(_slice(line, columns, "bp") or ""),
        "weight_kg": _num(_slice(line, columns, "weight") or ""),
        "margin": _slice(line, columns, "margin"),
        "sp_odds": _num(_slice(line, columns, "sp") or ""),
        "win_dividend": _num(_slice(line, columns, "win") or ""),
        "place_dividend": _num(_slice(line, columns, "place") or ""),
        "time_s": _num(_slice(line, columns, "time") or ""),
        "rating": _int(_slice(line, columns, "rating") or ""),
    }


def _column_map(table) -> dict[str, int]:
    """Map our field names to the column indexes of the MTC race table."""
    labels: dict[str, int] = {}
    for index, cell in enumerate(table.find_all("th")):
        text = _clean(cell.get_text(" ")).lower()
        for key, prefixes in HEADER_KEYS:
            if key in labels:
                continue
            if any(text.startswith(prefix) for prefix in prefixes):
                labels[key] = index
                break
    return labels


def parse_mtc_race_page(html: str, default_date=None) -> tuple[dict, list[str]]:
    """Parse a saved MTC race/result page into the shared dict shape."""
    from pipeline.parsing import parse_date, parse_time

    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []
    flat = _clean(soup.get_text(" "))

    table = soup.find("table", class_=lambda c: c and "race-card-mtc" in (c or ""))
    if table is None:
        return {}, ["no MTC race card table found on the page"]

    date = None
    date_match = re.search(r"(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})", flat)
    if date_match:
        date = parse_date(date_match.group(1))
    meeting = MEETING_LINE.search(flat)
    distance_match = re.search(r"Distance\s*(\d{3,4})\s*m", flat, re.I)
    class_match = re.search(r"Race Class\s*([0-9]{1,3}\s*-\s*[0-9]{1,3}|[A-Z0-9 \-/]{2,24})", flat, re.I)
    win_time_match = re.search(r"WinTime:?\s*(\d+:\d+(?:\.\d+)?)", flat, re.I)
    time_label = re.search(r"Race\s+\d+\s*-\s*(\d{1,2}:\d{2})", flat)

    labels = _column_map(table)
    runners: list[dict] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells or "horse" not in labels or labels["horse"] >= len(cells):
            continue

        def cell_text(key: str) -> str:
            index = labels.get(key)
            if index is None or index >= len(cells):
                return ""
            return _clean(cells[index].get_text(" "))

        horse_cell = cells[labels["horse"]]
        link = horse_cell.find("a")
        raw_name = _clean(link.get_text(" ") if link else horse_cell.get_text(" "))
        if not raw_name:
            continue
        external_id = None
        if link is not None and link.get("href"):
            matched = HORSE_LINK.search(link["href"])
            if matched:
                external_id = matched.group(2)
        prefix = re.match(r"^(\d+)\.", raw_name)
        trainer, jockey, claim = _split_trainer_jockey(
            cells[labels["people"]] if "people" in labels and labels["people"] < len(cells) else None
        )
        body_weight, body_delta = parse_hwt(cell_text("hwt"))

        runners.append({
            "finish_position": _int(cell_text("fp")) if "fp" in labels else None,
            "saddle_no": int(prefix.group(1)) if prefix else None,
            "horse": SADDLE_PREFIX.sub("", raw_name).strip(),
            "external_id": external_id,
            "trainer": trainer,
            "jockey": jockey,
            "claim_kg": claim,
            "gear": cell_text("gear") or None,
            "body_weight_kg": body_weight,
            "body_weight_delta": body_delta,
            "barrier": _int(cell_text("bp")),
            "weight_kg": _num(cell_text("weight")),
            "margin": cell_text("margin") or None,
            "sp_odds": _num(cell_text("sp")),
            "win_dividend": _num(cell_text("win")),
            "place_dividend": _num(cell_text("place")),
            "time_s": _num(cell_text("time")),
            "rating": _int(cell_text("rating")),
        })

    if not runners:
        warnings.append("race card table had no runner rows")

    parsed = {
        "source": "mtc-html",
        "meeting_no": int(meeting.group(1)) if meeting else None,
        "date": date or default_date,
        "race_no": _race_no_from_soup(soup, html),
        "race_name": _race_name_from_html(html),
        "distance_m": int(distance_match.group(1)) if distance_match else None,
        "race_class": _clean(class_match.group(1)) if class_match else None,
        "prize": _prize_from_text(flat),
        "race_time_label": time_label.group(1) if time_label else None,
        "win_time_s": parse_time(win_time_match.group(1)) if win_time_match else None,
        "runners": runners,
        "tote_dividends": _parse_dividends(soup),
        "sectional_times": _parse_sectionals_from_soup(soup) or _parse_sectionals(flat),
        "warnings": warnings,
    }
    return parsed, warnings