LAKH = 1_00_000
CRORE = 1_00_00_000


def format_value(value, unit: str, is_delta: bool = False, spoken: bool = False) -> str:
    """The one place a metric's own value gets turned into text.

    unit is a metric's declared unit (currency, count, percent) from
    metrics.yaml - not to be confused with a relative percent-change
    figure (e.g. "revenue rose 12%"), which has no fixed unit of its own
    and is formatted separately, at the call site, with plain %.1f.

    is_delta only matters for percent: an absolute value is a rate
    ("5.46%"), but the difference between two rates is stated in
    percentage points ("3.5 percentage points"), never "percent" again,
    to avoid the classic relative-vs-absolute percent confusion.

    spoken=True gives the words a text-to-speech voice should read
    ("50.8 lakh rupees") instead of the written display form ("Rs 50.81
    lakh"). Card headlines and delta text keep the display form; only
    narration_seed - what the agent actually says - uses spoken=True.
    """
    if value is None:
        return "n/a"

    if unit == "currency":
        return _format_currency(value, spoken)
    if unit == "count":
        return _format_count(value)
    if unit == "percent":
        return _format_percent(value, is_delta, spoken)
    return str(value)


def _spoken_scale(value: float, decimals: int = 1) -> str:
    # "5.0" reads awkwardly aloud; say "5" once rounding lands on a whole
    # number (4.998 rounds to "5.0" at 1 decimal, so check the rounded
    # value, not the raw one).
    rounded = round(value, decimals)
    if rounded == int(rounded):
        return f"{int(rounded)}"
    return f"{rounded:.{decimals}f}"


def _format_currency(value: float, spoken: bool) -> str:
    sign = "-" if value < 0 else ""
    v = abs(value)

    if spoken:
        if v >= CRORE:
            # crore amounts are large enough that 1 decimal loses real
            # precision (1.2 vs 1.3 crore is a 1,00,000 rupee gap), and
            # round(x, 1) can land on a banker's-rounding surprise right at
            # a clean value like 1.25 -> 1.2. Use 2 decimals here.
            return f"{sign}{_spoken_scale(v / CRORE, decimals=2)} crore rupees"
        if v >= LAKH:
            return f"{sign}{_spoken_scale(v / LAKH)} lakh rupees"
        if v >= 1_000:
            return f"{sign}{_spoken_scale(v / 1_000)} thousand rupees"
        return f"{sign}{v:.0f} rupees"

    if v >= CRORE:
        return f"{sign}Rs {v / CRORE:.2f} crore"
    if v >= LAKH:
        return f"{sign}Rs {v / LAKH:.2f} lakh"
    if v >= 1_000:
        return f"{sign}Rs {v / 1_000:.1f} thousand"
    return f"{sign}Rs {v:.0f}"


def _format_count(value: float) -> str:
    # same words either way - "N units" already reads fine aloud.
    sign = "-" if value < 0 else ""
    v = abs(value)
    if float(v).is_integer():
        return f"{sign}{int(v)} units"
    return f"{sign}{v:.1f} units"


def _format_percent(value: float, is_delta: bool, spoken: bool) -> str:
    # stored as a fraction in [0, 1]; convention fixed here, used everywhere.
    pct = value * 100
    if is_delta:
        sign = "-" if pct < 0 else ""
        return f"{sign}{abs(pct):.1f} percentage points"
    if spoken:
        return f"{pct:.2f} percent"
    return f"{pct:.2f}%"
