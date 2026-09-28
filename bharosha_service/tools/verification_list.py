"""Generates REFERRAL_VERIFICATION.md — every number Bharosha can hand out.

    python tools/verification_list.py

FOR THE PERSON DIALLING. "Does it ring" is not the test. Each row states what
Bharosha CLAIMS the number does and what hours it claims, because those claims
are what a woman acts on. A number that rings but is not free, not 24 hours, not
confidential, or not the service the app named is a failure the same as a dead
line — 16430 rang for months after it stopped being the GBV helpline.

Generated, not written, so it cannot fall behind referrals.py. Re-run it after
any change to the referral list and check the result back in.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import referrals  # noqa: E402

OUT = ROOT / "REFERRAL_VERIFICATION.md"

# What each number is claimed to be, in the app's own words, and therefore what
# the caller has to confirm. Keyed by number so a new helpline fails loudly here
# rather than being quietly omitted from the list someone is dialling.
CLAIMS: dict[str, list[str]] = {
    "999": [
        "Answers 24 hours",
        "Free to call from any network",
        "Reaches police, fire AND ambulance from this one number",
        "Operator can dispatch to a caller's location",
    ],
    "109": [
        "Answers 24 hours",
        "Free to call from any network",
        "Confidential — ask explicitly what is recorded and who can see it",
        "Takes complaints of violence, abuse and harassment directly",
        "Takes WORKPLACE harassment specifically (the disclosure script says so)",
        "Can trace a caller's location and send local police — this is claimed "
        "in the emergency script, so confirm it is still true",
        "Can refer on to protection and social services",
    ],
    "16263": [
        "Answers 24 hours",
        "Free to call",
        "Is Shastho Batayon, the DGHS health line — NOT a GBV service",
        "Gives medical advice from a doctor and can send an ambulance",
        "URGENT: press reports say staff have gone unpaid and closure was "
        "threatened. Confirm the service is actually operating.",
    ],
    "1098": [
        "Answers 24 hours",
        "Free to call",
        "Confidential",
        "Takes reports about a child from an ADULT, not only from children",
        "Covers child marriage, not only physical abuse",
    ],
    "333": [
        "Answers 24 hours",
        "Cost to call — confirm whether it is free",
        "Can direct a caller to local officials",
    ],
}

KAAN_PETE_ROI_CLAIMS = [
    f"Answers during {referrals.KAAN_PETE_ROI_HOURS_EN} — and NOT outside them",
    "Emotional support from trained volunteers",
    "Is an ordinary mobile number, so normal call charges apply. The suicide "
    "script says this, so confirm it is still a mobile number.",
    "What happens OUTSIDE those hours: ringing with no answer, a recorded "
    "message, or a diverted line? Someone in crisis will find out at 4am.",
]


def main() -> int:
    lines: list[str] = []
    w = lines.append

    w("# Referral verification list")
    w("")
    w(f"Generated {date.today().isoformat()} by `tools/verification_list.py` "
      "from `app/referrals.py`. Do not edit by hand — re-run it.")
    w("")
    w("## Why this exists")
    w("")
    w("Bharosha is a referral system. Every safety reply it gives ends in one "
      "of these numbers, and none of them has been dialled by a person. If a "
      "number is wrong the app does not fail neutrally: it sends someone "
      "somewhere useless at the worst moment of her life, and she concludes "
      "that help does not work.")
    w("")
    w("16430 was in this app as the GBV helpline after it had already been "
      "replaced. It was caught by a document, not by testing.")
    w("")
    w("## How to verify")
    w("")
    w("**Ringing is not a pass.** For each number, confirm every claim listed "
      "under it. Those claims are what the app tells people, so they are what "
      "has to be true. Where a claim turns out to be wrong, the fix is to "
      "change `app/referrals.py` — not to leave the number in with the wrong "
      "description.")
    w("")
    w("Call from a mobile on a normal network, not a landline or VoIP. Note "
      "the date and the time of day, because several of these claim 24-hour "
      "service and the failure mode is usually at night.")
    w("")

    missing = [
        h.number for h in referrals.NATIONAL_HELPLINES if h.number not in CLAIMS
    ]
    if missing:
        raise SystemExit(f"no claims written for {missing} — add them to CLAIMS")

    w("## National helplines")
    w("")
    for line in referrals.NATIONAL_HELPLINES:
        w(f"### {line.number} — {line.name_en}")
        w("")
        state = "yes" if line.in_emergency_script else "NO — deliberately excluded"
        w(f"- **In crisis scripts:** {state}")
        w(f"- **Shown in the app as:** {line.desc_en}")
        w("")
        w("Confirm:")
        w("")
        for claim in CLAIMS[line.number]:
            w(f"- [ ] {claim}")
        w("")
        w("| result | |")
        w("|---|---|")
        w("| Answered? | |")
        w("| Date and time called | |")
        w("| Who answered, and what they said the service is | |")
        w("| Claims that were WRONG | |")
        w("")

    w(f"### {referrals.KAAN_PETE_ROI_NUMBER} — Kaan Pete Roi")
    w("")
    w("- **In crisis scripts:** yes — the suicide-risk reply, after 999")
    w(f"- **Hours claimed:** {referrals.KAAN_PETE_ROI_HOURS_EN}")
    w("")
    w("Confirm:")
    w("")
    for claim in KAAN_PETE_ROI_CLAIMS:
        w(f"- [ ] {claim}")
    w("")
    w("| result | |")
    w("|---|---|")
    w("| Answered in hours? | |")
    w("| Answered OUT of hours? (call after 3am) | |")
    w("| Date and time called | |")
    w("| Claims that were WRONG | |")
    w("")

    w("## Safeguarding focal points")
    w("")
    w("These are organisation staff, not helplines. Bharosha names them in the "
      "disclosure and reporting replies, via the app's Important Numbers "
      "screen. Confirm the person still holds the safeguarding role and that "
      "the inbox is monitored — a focal point who has left the organisation is "
      "the same failure as a dead number.")
    w("")
    w("| Organisation | Number | Email | Rings? | Right person? | Inbox monitored? |")
    w("|---|---|---|---|---|---|")
    for point in referrals.SAFEGUARDING_FOCAL_POINTS:
        w(f"| {point.organisation} | {point.number} | {point.email} | | | |")
    w("")
    w(f"### {referrals.SAFEGUARDING_EMAIL}")
    w("")
    w("The WaterAid Bangladesh safeguarding inbox, named in the disclosure and "
      "reporting replies. Confirm it accepts external mail, that someone reads "
      "it, and that there is a stated response time.")
    w("")
    w("- [ ] Test email sent and acknowledged")
    w("")
    w("## Until this comes back")
    w("")
    w("`app/referrals.py` carries `VERIFICATION_STATUS`, which the test suite "
      "checks. It says UNVERIFIED. Change it only when this document comes "
      "back completed.")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT.name}: {len(referrals.NATIONAL_HELPLINES) + 1} numbers, "
        f"{len(referrals.SAFEGUARDING_FOCAL_POINTS)} focal points"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
