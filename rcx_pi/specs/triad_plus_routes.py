# rcx_pi/specs/triad_plus_routes.py
from __future__ import annotations

from typing import Dict

TRIAD_PLUS_ROUTE_OVERRIDES: Dict[str, str] = {
    # core-ish but edgy
    "[null,[1/0]]": "Ra",
    "[inf,[1/0]]": "Lobe",

    "[liar,1/0]": "Lobe",
    "[Gödel,1/0_engine]": "Ra",

    "[white_light,paradox]": "Ra",
    "[I_am_true,null]": "Ra",

    "[collapse]": "Sink",
    "[expand]": "Ra",
    "[flatten]": "Sink",
}
