"""
date_utils.py — Human-oriented date/time parsing for Hermes MCP skill servers.

PURPOSE
-------
Many AI agents have an unreliable grasp of the current date and time. Rather
than asking agents to compute and pass ISO timestamps, the server tools accept
natural-language phrases and resolve them here against the real system clock.

ISO strings (2026-06-11, 2026-06-11T09:00:00) still work as-is for
well-behaved agents or direct API callers.

PUBLIC API
----------
  parse_dt(value, tz_name, end_of_day=False) -> str
      Resolve any date/time phrase to an ISO datetime string.
      Used for single-point parameters: start, end, date.

  parse_date_range(value, tz_name) -> tuple[str, str]
      Resolve a range phrase to (start_iso, end_iso).
      Used when a single parameter encodes a full range, e.g. "last week",
      "this month", "yesterday", "within the last 7 days".

  is_range_phrase(value) -> bool
      Return True if value looks like a range phrase that parse_date_range
      should handle rather than parse_dt.

SUPPORTED PHRASES (non-exhaustive)
-----------------------------------
ISO / structured:
  "2026-06-11", "2026-06-11T09:00:00", "2026-06-11T09:00:00-05:00"

Point-in-time (resolved by dateparser):
  "today", "now", "tomorrow", "yesterday"
  "next Monday", "last Friday", "this Thursday"
  "June 15", "June 15 at 3pm", "in 2 hours", "3 hours ago"
  "next week Monday", "end of day", "noon", "midnight"

Preposition-prefixed (stripped before parsing):
  "since yesterday", "as of last Monday", "from next Tuesday"
  "through next Friday", "until end of month", "up to tomorrow"
  "starting Monday", "ending next Thursday"

Rolling windows (resolved against now):
  "within the last 7 days", "past 3 days", "last 24 hours"
  "within the past week", "in the last 2 weeks", "last 30 days"
  "past month", "last 6 months", "within 48 hours"

Named calendar periods (Sun–Sat week boundaries):
  "last week", "this week", "next week"
  "last month", "this month", "next month"
  "last year", "this year", "next year"
  "last quarter", "this quarter", "next quarter"
  "yesterday" (as range: full day)
  "today" (as range: full day so far)
  "tomorrow" (as range: full day)

WEEK CONVENTION
---------------
  Week start: Sunday 00:00:00
  Week end:   Saturday 23:59:59
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone as _tz_module, time as _time
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Lazy imports (dateparser is slow to import — only loaded on first use)
# ---------------------------------------------------------------------------
_dateparser  = None
_pytz        = None
_relativedelta = None

def _get_dateparser():
    global _dateparser
    if _dateparser is None:
        import dateparser as _dp
        _dateparser = _dp
    return _dateparser

def _get_pytz():
    global _pytz
    if _pytz is None:
        try:
            import pytz as _p
            _pytz = _p
        except ImportError:
            _pytz = None
    return _pytz

def _get_relativedelta():
    """Return (relativedelta class, weekday constants dict)."""
    global _relativedelta
    if _relativedelta is None:
        from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
        _relativedelta = (relativedelta, {'monday': MO, 'tuesday': TU, 'wednesday': WE,
                                          'thursday': TH, 'friday': FR, 'saturday': SA,
                                          'sunday': SU})
    return _relativedelta


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------
def _tz_obj(tz_name: str):
    """Return a tzinfo object for the given tz_name string."""
    pytz = _get_pytz()
    if pytz:
        try:
            return pytz.timezone(tz_name)
        except Exception:
            pass
    # Fall back to UTC offset parsing or zoneinfo (Python 3.9+)
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        pass
    return _tz_module.utc


def _now_in_tz(tz_name: str) -> datetime:
    """Return timezone-aware 'now' in the specified timezone."""
    tz = _tz_obj(tz_name)
    return datetime.now(tz)


def _midnight(dt: datetime) -> datetime:
    """Return dt at 00:00:00, same tzinfo."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    """Return dt at 23:59:59, same tzinfo."""
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)


def _fmt(dt: datetime) -> str:
    """Format datetime as ISO string without microseconds."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Pre-processing: strip leading prepositions
# ---------------------------------------------------------------------------
_STRIP_PREFIXES = re.compile(
    r"^\s*(since|from|as\s+of|starting(?:\s+from)?|beginning(?:\s+from)?)\s+",
    re.IGNORECASE,
)
_STRIP_SUFFIXES = re.compile(
    r"\s*(through|until|up\s+to|ending(?:\s+on)?|thru)\s+",
    re.IGNORECASE,
)

def _strip_start_prefix(value: str) -> str:
    return _STRIP_PREFIXES.sub("", value).strip()

def _strip_end_prefix(value: str) -> str:
    # "through next Friday" -> "next Friday"
    m = re.match(
        r"^\s*(through|until|up\s+to|ending(?:\s+on)?|thru)\s+(.+)$",
        value, re.IGNORECASE,
    )
    return m.group(2).strip() if m else value.strip()


# ---------------------------------------------------------------------------
# Rolling-window detection
# ---------------------------------------------------------------------------
# Matches: "within the last 7 days", "past 3 weeks", "last 24 hours",
#          "in the last 2 months", "within 48 hours", "past month",
#          "within the past N unit"
# Two sub-patterns:
#   A) optional within/the + last/past/in...last + optional N + unit
#   B) within (the)? N unit  (no last/past word needed)
_ROLLING_RE = re.compile(
    r"""
    (?:
        # Pattern A: "within the last 7 days", "past 3 weeks", "last 24 hours"
        (?:within\s+(?:the\s+)?)?
        (?:the\s+)?
        (?:past|last|in\s+(?:the\s+)?last)
        \s+
        (?:(\d+)\s+)?
        (second|minute|hour|day|week|month|year)s?
    |
        # Pattern B: "within 48 hours", "within the 48 hours", "within 2 weeks"
        within\s+(?:the\s+)?(\d+)\s+(second|minute|hour|day|week|month|year)s?
    )
    (?:\s+or\s+so)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_UNIT_DELTA = {
    "second": timedelta(seconds=1),
    "minute": timedelta(minutes=1),
    "hour":   timedelta(hours=1),
    "day":    timedelta(days=1),
    "week":   timedelta(weeks=1),
    "month":  timedelta(days=30),
    "year":   timedelta(days=365),
}

def _parse_rolling(value: str, tz_name: str) -> Optional[tuple[str, str]]:
    """If value is a rolling-window phrase, return (start_iso, end_iso). Else None."""
    m = _ROLLING_RE.search(value)
    if not m:
        return None
    # Group 1,2 = Pattern A; Group 3,4 = Pattern B
    if m.group(2):
        n_str, unit = m.group(1), m.group(2).lower()
    else:
        n_str, unit = m.group(3), m.group(4).lower()
    n = int(n_str) if n_str else 1
    delta = _UNIT_DELTA.get(unit, timedelta(days=1)) * n
    now = _now_in_tz(tz_name)
    start = now - delta
    return _fmt(start), _fmt(now)


# ---------------------------------------------------------------------------
# Named calendar period detection
# ---------------------------------------------------------------------------
_PERIOD_RE = re.compile(
    r"^\s*(last|this|next)\s+(week|month|quarter|year)\s*$",
    re.IGNORECASE,
)
_DAY_PHRASE_RE = re.compile(
    r"^\s*(yesterday|today|tomorrow)\s*$",
    re.IGNORECASE,
)

def _week_bounds(ref: datetime, which: str) -> tuple[datetime, datetime]:
    """Return (Sunday 00:00, Saturday 23:59) for last/this/next week relative to ref."""
    # Find most recent Sunday (weekday 6 = Sunday in Python when week starts Monday,
    # but isoweekday: Mon=1 … Sun=7 — we want Sun as first day)
    # Python weekday(): Mon=0, Sun=6
    days_since_sunday = ref.weekday() + 1  # Mon=1..Sat=6, Sun=0 -> +1 gives Mon=2..Sun=1 hmm
    # Simpler: isoweekday Sun=7, use (isoweekday % 7) to get offset from Sunday
    offset = ref.isoweekday() % 7   # Sun=0, Mon=1, ..., Sat=6
    this_sunday = _midnight(ref) - timedelta(days=offset)
    this_saturday = this_sunday + timedelta(days=6)
    this_saturday = _end_of_day(this_saturday)

    if which == "this":
        return this_sunday, this_saturday
    elif which == "last":
        last_sunday = this_sunday - timedelta(weeks=1)
        last_saturday = _end_of_day(last_sunday + timedelta(days=6))
        return last_sunday, last_saturday
    else:  # next
        next_sunday = this_sunday + timedelta(weeks=1)
        next_saturday = _end_of_day(next_sunday + timedelta(days=6))
        return next_sunday, next_saturday


def _month_bounds(ref: datetime, which: str) -> tuple[datetime, datetime]:
    import calendar
    if which == "this":
        year, month = ref.year, ref.month
    elif which == "last":
        year = ref.year if ref.month > 1 else ref.year - 1
        month = ref.month - 1 if ref.month > 1 else 12
    else:  # next
        year = ref.year if ref.month < 12 else ref.year + 1
        month = ref.month + 1 if ref.month < 12 else 1
    tz = ref.tzinfo
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
    last_day = calendar.monthrange(year, month)[1]
    end = _end_of_day(datetime(year, month, last_day, tzinfo=tz))
    return start, end


def _quarter_bounds(ref: datetime, which: str) -> tuple[datetime, datetime]:
    import calendar
    current_q = (ref.month - 1) // 3  # 0..3
    tz = ref.tzinfo

    if which == "this":
        q = current_q
        year = ref.year
    elif which == "last":
        q = current_q - 1
        year = ref.year
        if q < 0:
            q = 3
            year -= 1
    else:  # next
        q = current_q + 1
        year = ref.year
        if q > 3:
            q = 0
            year += 1

    start_month = q * 3 + 1
    end_month = start_month + 2
    start = datetime(year, start_month, 1, 0, 0, 0, tzinfo=tz)
    last_day = calendar.monthrange(year, end_month)[1]
    end = _end_of_day(datetime(year, end_month, last_day, tzinfo=tz))
    return start, end


def _year_bounds(ref: datetime, which: str) -> tuple[datetime, datetime]:
    tz = ref.tzinfo
    if which == "this":
        year = ref.year
    elif which == "last":
        year = ref.year - 1
    else:
        year = ref.year + 1
    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=tz)
    end = _end_of_day(datetime(year, 12, 31, tzinfo=tz))
    return start, end


def _parse_named_period(value: str, tz_name: str) -> Optional[tuple[str, str]]:
    """If value is a named calendar period, return (start_iso, end_iso). Else None."""
    # Day phrases: yesterday / today / tomorrow
    m = _DAY_PHRASE_RE.match(value)
    if m:
        word = m.group(1).lower()
        now = _now_in_tz(tz_name)
        if word == "yesterday":
            d = _midnight(now) - timedelta(days=1)
        elif word == "today":
            d = _midnight(now)
        else:  # tomorrow
            d = _midnight(now) + timedelta(days=1)
        return _fmt(d), _fmt(_end_of_day(d))

    # Period phrases: last/this/next week/month/quarter/year
    m = _PERIOD_RE.match(value)
    if not m:
        return None
    which, period = m.group(1).lower(), m.group(2).lower()
    now = _now_in_tz(tz_name)

    if period == "week":
        s, e = _week_bounds(now, which)
    elif period == "month":
        s, e = _month_bounds(now, which)
    elif period == "quarter":
        s, e = _quarter_bounds(now, which)
    else:  # year
        s, e = _year_bounds(now, which)
    return _fmt(s), _fmt(e)


# ---------------------------------------------------------------------------
# ISO fast-path detection
# ---------------------------------------------------------------------------
_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?([+-]\d{2}:?\d{2}|Z)?)?$"
)

def _is_iso(value: str) -> bool:
    return bool(_ISO_RE.match(value.strip()))


def _normalise_iso(value: str, end_of_day: bool = False) -> str:
    """Add T00:00:00 / T23:59:59 to bare dates; leave datetimes alone."""
    v = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        suffix = "T23:59:59" if end_of_day else "T00:00:00"
        return v + suffix
    return v


# ---------------------------------------------------------------------------
# is_range_phrase
# ---------------------------------------------------------------------------
def is_range_phrase(value: str) -> bool:
    """
    Return True if value is a range phrase that parse_date_range should handle.

    Examples that return True:
      "last week", "this month", "next quarter", "yesterday", "today",
      "within the last 7 days", "past 3 weeks", "last 24 hours"
    """
    v = value.strip()
    if _is_iso(v):
        return False
    if _ROLLING_RE.search(v):
        return True
    if _PERIOD_RE.match(v) or _DAY_PHRASE_RE.match(v):
        return True
    return False


# ---------------------------------------------------------------------------
# Weekday resolver (dateparser cannot handle next/last/this + weekday)
# ---------------------------------------------------------------------------
_WEEKDAY_PHRASE_RE = re.compile(
    r"^(next|last|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"(\s+at\s+.+)?$",
    re.IGNORECASE,
)

def _parse_weekday_phrase(value: str, tz_name: str) -> Optional[datetime]:
    """
    Handle 'next Monday', 'last Friday', 'this Thursday', 'next Monday at 9am', etc.
    Returns a timezone-aware datetime or None if value doesn't match the pattern.
    """
    m = _WEEKDAY_PHRASE_RE.match(value.strip())
    if not m:
        return None

    which      = m.group(1).lower()
    wd_key     = m.group(2).lower()
    time_part  = m.group(3)  # e.g. " at 9am", or None

    relativedelta, WDMAP = _get_relativedelta()
    now = _now_in_tz(tz_name)
    now_naive = now.replace(tzinfo=None)

    if which == "next":
        # strictly after today
        base = (now_naive + timedelta(days=1)) + relativedelta(weekday=WDMAP[wd_key])
    elif which == "last":
        # strictly before today
        base = (now_naive - timedelta(days=1)) + relativedelta(weekday=WDMAP[wd_key](-1))
    else:  # "this"
        # today if matches, else next occurrence
        base = now_naive + relativedelta(weekday=WDMAP[wd_key])

    base = base.replace(hour=0, minute=0, second=0, microsecond=0)

    if time_part:
        tp = time_part.strip().lstrip("at").strip()
        dp = _get_dateparser()
        t = dp.parse(tp, languages=["en"], settings={"PREFER_DATES_FROM": "future"})
        if t:
            base = base.replace(hour=t.hour, minute=t.minute, second=t.second)

    return base.replace(tzinfo=now.tzinfo)


# ---------------------------------------------------------------------------
# dateparser fallback
# ---------------------------------------------------------------------------
def _dp_parse(value: str, tz_name: str, prefer_future: bool = True) -> Optional[datetime]:
    """Parse value with dateparser, anchored to real system clock."""
    dp = _get_dateparser()
    settings = {
        "PREFER_DATES_FROM": "future" if prefer_future else "past",
        "TIMEZONE": tz_name,
        "TO_TIMEZONE": tz_name,
    }
    return dp.parse(value, languages=["en"], settings=settings)


# ---------------------------------------------------------------------------
# PUBLIC: parse_dt
# ---------------------------------------------------------------------------
def parse_dt(value: str, tz_name: str = "America/Chicago", end_of_day: bool = False) -> str:
    """
    Resolve a date/time value — ISO string or natural-language phrase — to an
    ISO datetime string (YYYY-MM-DDTHH:MM:SS), anchored to the real system clock.

    Parameters
    ----------
    value      : date/time string, e.g. "2026-06-11", "tomorrow", "next Monday at 9am"
    tz_name    : IANA timezone name (default "America/Chicago")
    end_of_day : if True and value is a bare date phrase, resolve to 23:59:59 instead
                 of 00:00:00 (useful for 'end' parameters)

    Supported input formats
    -----------------------
    ISO:          "2026-06-11", "2026-06-11T09:00:00"
    Preposition:  "since yesterday", "through next Friday", "as of last Monday",
                  "from next Tuesday", "until end of month"
    Relative:     "today", "tomorrow", "yesterday", "now"
                  "next Monday", "last Friday", "this Thursday"
                  "in 2 hours", "3 hours ago", "next week Monday"
                  "June 15", "June 15 at 3pm", "noon", "midnight"

    Note: for range phrases like "last week" or "within the past 7 days", use
    parse_date_range() instead.

    Raises
    ------
    ValueError if the value cannot be parsed.
    """
    if not value or not value.strip():
        raise ValueError("date/time value must not be empty")

    v = value.strip()

    # 1. ISO fast-path
    if _is_iso(v):
        return _normalise_iso(v, end_of_day=end_of_day)

    # 2. Strip start/end prepositions depending on context
    if end_of_day:
        v = _strip_end_prefix(v)
    else:
        v = _strip_start_prefix(v)

    # 3. Re-check ISO after strip
    if _is_iso(v):
        return _normalise_iso(v, end_of_day=end_of_day)

    # 4. Named single-day phrases (today/yesterday/tomorrow) -> return start or end of that day
    m = _DAY_PHRASE_RE.match(v)
    if m:
        word = m.group(1).lower()
        now = _now_in_tz(tz_name)
        if word == "yesterday":
            d = _midnight(now) - timedelta(days=1)
        elif word == "today":
            d = _midnight(now)
        else:  # tomorrow
            d = _midnight(now) + timedelta(days=1)
        return _fmt(_end_of_day(d) if end_of_day else d)

    # 5. next/last/this + weekday (+ optional time): dateparser can't handle these
    dt = _parse_weekday_phrase(v, tz_name)
    if dt:
        if end_of_day and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            dt = _end_of_day(dt)
        return _fmt(dt)

    # 6. dateparser — handles: "in 2 hours", "June 15", "noon", "3 hours ago",
    #    bare weekday names ("Monday"), "beginning of next month", etc.
    dt = _dp_parse(v, tz_name, prefer_future=not end_of_day)
    if dt:
        if end_of_day and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            dt = _end_of_day(dt)
        return _fmt(dt)

    raise ValueError(
        f"Could not parse date/time value: {value!r}. "
        "Use a natural-language phrase (e.g. 'yesterday', 'next Monday', 'last week') "
        "or an ISO string (e.g. '2026-06-11' or '2026-06-11T09:00:00')."
    )


# ---------------------------------------------------------------------------
# PUBLIC: parse_date_range
# ---------------------------------------------------------------------------
def parse_date_range(value: str, tz_name: str = "America/Chicago") -> tuple[str, str]:
    """
    Resolve a range phrase to (start_iso, end_iso), anchored to the real system clock.

    Parameters
    ----------
    value   : range phrase, e.g. "last week", "this month", "within the last 7 days",
              "yesterday", "today", "next quarter"
    tz_name : IANA timezone name (default "America/Chicago")

    Returns
    -------
    (start_iso, end_iso) as "YYYY-MM-DDTHH:MM:SS" strings

    Supported range phrases
    -----------------------
    Day ranges:         "yesterday", "today", "tomorrow"
    Week ranges:        "last week", "this week", "next week"
                        (Sunday 00:00:00 — Saturday 23:59:59)
    Month ranges:       "last month", "this month", "next month"
    Quarter ranges:     "last quarter", "this quarter", "next quarter"
    Year ranges:        "last year", "this year", "next year"
    Rolling windows:    "within the last 7 days", "past 3 weeks",
                        "last 24 hours", "in the last 2 months",
                        "within 48 hours", "past month"

    Raises
    ------
    ValueError if the value cannot be resolved to a range.
    """
    if not value or not value.strip():
        raise ValueError("range value must not be empty")

    v = value.strip()

    # 1. Named calendar periods first — "last week" means Sun–Sat calendar week,
    #    NOT a rolling 7-day window. Must run before rolling regex since "last week"
    #    would otherwise match _ROLLING_RE pattern A.
    result = _parse_named_period(v, tz_name)
    if result:
        return result

    # 2. Rolling windows — "within the last week", "past 7 days", "last 24 hours", etc.
    #    These phrases have additional words (within, past, N) that distinguish them
    #    from bare "last week/month/year" calendar periods.
    result = _parse_rolling(v, tz_name)
    if result:
        return result

    # 3. Fallback: try dateparser for the start, end = start + 1 day
    try:
        start_iso = parse_dt(v, tz_name, end_of_day=False)
        end_iso   = parse_dt(v, tz_name, end_of_day=True)
        return start_iso, end_iso
    except ValueError:
        pass

    raise ValueError(
        f"Could not resolve range phrase: {value!r}. "
        "Supported: 'last week', 'this month', 'next quarter', 'yesterday', "
        "'within the last 7 days', 'past 3 weeks', etc."
    )
