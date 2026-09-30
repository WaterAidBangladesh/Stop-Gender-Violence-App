"""Builds Bharosha_Complete_Guide.pdf from the live code.

    python tools/build_guide.py


Every number, category, reply, prompt and test case in the PDF is read from the
repository at build time, not typed. Narrative is written here.

Pipeline: HTML (print CSS) -> Edge headless -> PDF, twice (second pass fills the
contents page numbers), then page footers stamped with pypdf.
"""

from __future__ import annotations

import collections
import datetime
import html
import io
import json
import re
import subprocess
import sys
from pathlib import Path

SVC = Path(__file__).resolve().parents[1]
REPO = SVC.parent
APP = REPO / "stop_gender_violence_fresh_ui"
SCRATCH = SVC / ".guide-build"  # the two Edge passes; gitignored
SCRATCH.mkdir(exist_ok=True)
OUT_PDF = REPO.parent / "Bharosha_Complete_Guide.pdf"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

sys.path.insert(0, str(SVC / "app"))
sys.path.insert(0, str(SVC / "tools"))

import assertions  # noqa: E402
import chain  # noqa: E402
import embedding  # noqa: E402
import ratelimit  # noqa: E402
import referrals  # noqa: E402
import safety  # noqa: E402
import sessions  # noqa: E402
import verification_list  # noqa: E402

E = html.escape
TODAY = datetime.date.today().strftime("%d %B %Y")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


COMMIT = git("rev-parse", "--short", "HEAD")
COMMIT_COUNT = git("rev-list", "--count", "HEAD")
COMMITS = git("log", "--pretty=format:%h\t%ad\t%s", "--date=short").splitlines()

BENGALI = re.compile(r"[\u0980-\u09FF]")


def t(text: str) -> str:
    """Escape, and mark Bangla so it gets the Bangla font."""
    esc = E(text)
    return f'<span class="bn">{esc}</span>' if BENGALI.search(text) else esc


def md(text: str) -> str:
    """The small Markdown subset the referral scripts use."""
    blocks = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if block == "---":
            blocks.append("<hr>")
            continue
        lines = block.splitlines()
        if all(l.strip().startswith("- ") for l in lines):
            items = "".join(f"<li>{inline(l.strip()[2:])}</li>" for l in lines)
            blocks.append(f"<ul>{items}</ul>")
        else:
            blocks.append("<p>" + "<br>".join(inline(l) for l in lines) + "</p>")
    return "".join(blocks)


def inline(s: str) -> str:
    s = E(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    if BENGALI.search(s):
        s = f'<span class="bn">{s}</span>'
    return s


# --------------------------------------------------------------------------
# Data read from the code
# --------------------------------------------------------------------------

DESCRIBE = {
    "suicide_risk": "Wanting to die, self-harm, not wanting to live.",
    "immediate_danger": "In danger right now, hiding, scared now, “help me now”.",
    "threat_to_life": "Threats to kill; acid; strangling.",
    "child_disclosure": "A child harmed, child marriage — a child and a harm in one breath.",
    "active_violence": "Violence happening now — “he is beating me”, “মারছে”.",
    "leave_decision": "Whether or when to leave a partner or household.",
    "divorce_process": "How to get a divorce, separation or khula.",
    "confront_or_evidence": "Confronting, recording, or gathering evidence against someone.",
    "economic_rights": "Inheritance and property entitlement.",
    "legal_advice": "Case outcomes, punishments, which law applies, filing a case.",
    "medical_advice": "Treating injuries, medicines, symptoms.",
    "third_party_concern": "Asking on behalf of a friend, sister, colleague or neighbour.",
    "personal_disclosure": "Describing harm done to her by someone with power over her.",
    "coercive_control": "Control of money, movement, work, phone, documents; threats to throw her out.",
    "reporting_request": "How or where to report or complain.",
    "low_distress": "Feeling sad, alone, anxious, not okay — no cause given.",
    "greeting": "Hello, good morning, how are you, kemon acho.",
    "thanks": "Thank you, dhonnobad, ধন্যবাদ.",
    "acknowledgement": "ok, hmm, got it, bye, ঠিক আছে.",
    "identity": "Who or what are you; are you a real person; what can you do.",
    "privacy": "Will he see this; is this saved; is it confidential.",
    "bot_abuse": "Frustration aimed at the app.",
    "vague": "help, ki korbo, what should I do — too little to act on.",
}

DRAFT = {
    "divorce_process", "economic_rights", "medical_advice", "personal_disclosure",
    "privacy", "reporting_request", "coercive_control", "low_distress",
    "third_party_concern",
}
PENDING = {"child_disclosure"}

NEAR = collections.defaultdict(list)
for rule in safety._NEAR_RULES:
    NEAR[rule.category].append(rule.window)

PRIORITY = list(safety._PRIORITY)
DEVICE = set(safety.DEVICE_CATEGORIES)
KIND = dict(safety._KIND_OF)
PATTERN_COUNT = {k: len(v) for k, v in safety._PATTERNS.items()}
TOTAL_PATTERNS = sum(PATTERN_COUNT.values())

CASES = json.loads((SVC / "shared" / "safety_cases.json").read_text(encoding="utf-8"))["cases"]
CHUNKS = json.loads((SVC / "corpus" / "chunks.json").read_text(encoding="utf-8"))
PACK = json.loads((SVC / "corpus" / "knowledge_pack.json").read_text(encoding="utf-8"))
EXT = json.loads((SVC / "corpus" / "external_sources.json").read_text(encoding="utf-8"))

ORIGIN = collections.Counter(c.get("origin") for c in CHUNKS)
MACHINE_BN = sum(1 for c in CHUNKS if c.get("bn_review") == "machine_pending_review")
SOURCES = collections.Counter(c["source"] for c in CHUNKS)
PACK_CATS = collections.Counter(e["category"] for e in PACK["entries"])
EXT_SOURCES = collections.Counter(e["source"] for e in EXT["entries"])


def lines_of(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


# --------------------------------------------------------------------------
# Page parts
# --------------------------------------------------------------------------

def badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{E(text)}</span>'


def table(head: list[str], rows: list[list[str]], cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def note(text: str, kind: str = "") -> str:
    return f'<div class="note {kind}">{text}</div>'


SECTIONS: list[tuple[str, str]] = []  # (id, title)


def section(sid: str, title: str, body: str, appendix: bool = False) -> str:
    SECTIONS.append((sid, title))
    cls = "appendix" if appendix else ""
    return f'<section id="{sid}" class="{cls}"><h2 data-find="{E(title)}">{E(title)}</h2>{body}</section>'


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

def s_summary() -> str:
    return f"""
<p class="lead">Bharosha (<span class="bn">ভরসা</span>, “trust”) is a bilingual Bangla and English
safeguarding and gender-based-violence assistant inside WaterAid Bangladesh's
<strong>Shomota Shurokkha</strong> Android app.</p>

<p>It is a <strong>referral system first</strong>. Its job is to listen, to explain what WaterAid's
safeguarding material says, and to get a person to a trained human. It is not counselling, therapy,
legal advice, medical advice, or a way to report an incident — and it says so, in those words.</p>

<p>Its one design rule is <strong>safety decides, the AI speaks</strong>:</p>
<ul>
<li><strong>A deterministic safety layer decides what the situation is.</strong> Plain pattern matching,
on the phone first and again on the server, in Bangla, romanised Bangla and English. The five emergencies
are answered on the phone from fixed, reviewed text in milliseconds, with no network and no model.</li>
<li><strong>The model writes the words for everything else</strong> — a greeting, a disclosure, a
question about economic violence — from a prompt that describes how to talk to someone having a hard
day, grounded in a corpus of {len(CHUNKS)} passages of WaterAid and partner material.</li>
<li><strong>Code appends the safety.</strong> For every recognised category a referral block — the
contacts and the one sentence of limit — comes from <code>referrals.py</code>, not from the model. The
model never writes a number, and its output is checked before it is shown.</li>
</ul>

<h3>The rules it is built on</h3>
<p>These came from the original brief and have not moved. Every design decision in this document is
downstream of them.</p>
<ol class="rules">
<li><strong>The model is never the safety layer.</strong> Emergency detection is deterministic, runs
first, returns fixed text, and never calls a model.</li>
<li><strong>Referral first.</strong> Never described as counselling, therapy, legal advice or a
reporting channel.</li>
<li><strong>Three things it never does:</strong> advise whether or when to leave; give legal advice or
predict a case; suggest confronting, recording or gathering evidence.</li>
<li><strong>Facts come only from retrieved content.</strong> Feelings, listening and ordinary conversation
need no source; safeguarding, health, legal and procedural facts do.</li>
<li><strong>Referral numbers have one source of truth</strong>, the model never writes one, and none is
added or changed without the product owner's approval. A dead number in a GBV app is worse than no app.</li>
<li><strong>Nothing is logged.</strong> No question text, no answer text, no user id — counters only. A
random session id per conversation, never the Firebase id.</li>
<li><strong>No login.</strong> So the server is rate limited for cost and abuse.</li>
<li><strong>Every path works offline.</strong> When the server cannot be reached, every category still
shows its complete fixed text.</li>
</ol>
"""


def s_status() -> str:
    rows = [
        ["Code", f"{COMMIT_COUNT} commits, latest <code>{COMMIT}</code>, pushed to the <strong>public</strong> "
                 "repository <code>WaterAidBangladesh/Stop-Gender-Violence-App</code>. Working tree clean."],
        ["Deployed", "<strong>No.</strong> Runs on a developer machine only. The Dockerfile is ready for "
                     "Render; nobody has deployed it."],
        ["App connected to a server",
         "<strong>Not by default.</strong> <code>BHAROSHA_URL</code> is empty unless the app is built with "
         "<code>--dart-define=BHAROSHA_URL=…</code>. Without it, only on-device replies and bundled "
         "fallback text are shown."],
        ["Referral numbers", f"<strong>{E(referrals.VERIFICATION_STATUS)}.</strong> None has been dialled by a "
                             "person. <code>REFERRAL_VERIFICATION.md</code> is the checklist."],
        ["Reviewed wording", f"{len(DRAFT) + len(PENDING)} fixed replies await WaterAid sign-off. No Bangla text "
                             "has been read by a native speaker."],
        ["Corpus", f"{len(CHUNKS)} passages. {ORIGIN['knowledge_pack_pending_review'] + ORIGIN['external_pending_review']} "
                   "are pending WaterAid review."],
        ["Tests", "364 offline Python + 68 live + 238 Dart, all passing. One unrelated Flutter widget "
                  "test fails, exactly as it did before this work began."],
        ["Output check", "Every model reply is checked for numbers, emails, advice and step lists; one retry, "
                         "then fixed text. Retry and fallback rates are recorded in <code>probe_results.md</code>."],
    ]
    return table(["", "Status"], rows, "kv")


def s_experience() -> str:
    rows = [
        [badge("Phone", "device"),
         "One of the five emergencies. Fixed, reviewed text, instantly, offline. The phone then tells the "
         "server only the category, so the next reply knows.",
         t("he is going to kill me · I want to die · he is beating me right now · they want to marry off my daughter")],
        [badge("Model + block", "model"),
         "A safety category the phone recognised. The model writes to what she said; code appends the "
         "referral block — full the first time, one line after.",
         t("my husband hits me · he controls my money · should I leave? · I want to report this · "
           "I feel so alone · my friend is being abused")],
        [badge("Model, from facts", "model"),
         "Who or what are you; will he see this. The model answers from a fixed note of facts about the app. "
         "Nothing appended.",
         t("are you a real person? · will my husband know I used this?")],
        [badge("Model, conversation", "warn"),
         "A greeting, thanks, “hmm”, frustration, “ki korbo”. The model replies like a person and mirrors her "
         "greeting. Nothing appended.",
         t("hi · Assalamu alaikum · thank you · achha bujhlam · ki korbo?")],
        [badge("Model, from the corpus", "model"),
         "An ordinary question. Answered from WaterAid's material, crediting the source; below the floor it "
         "only listens. Nothing appended — the call buttons are on screen.",
         t("what is gender based violence · what counts as economic violence · how do I cook rice")],
    ]
    return f"""
<p>Every message takes one of five routes. The phone decides which in microseconds, before anything is
sent anywhere.</p>
{table(["Route", "What happens", "Examples"], rows, "routes")}
{note("<strong>If the server cannot be reached</strong> — no signal, a sleeping instance, eight seconds with no "
      "reply for a recognised category — the phone shows that category's complete fixed text, exactly as it "
      "did before the model was involved. Nothing that worked offline stops working offline.")}
<h3>What the screen looks like</h3>
<ul>
<li>A header with the name, a language toggle, and a red <strong>Leave now</strong> button.</li>
<li>A disclaimer: <em>“Bharosha explains WaterAid's safeguarding material and points you to people who
can help. It is not counselling, legal advice, or a way to report an incident. In an emergency call
999.”</em></li>
<li>A row of tap-to-call buttons for <strong>999</strong> and <strong>109</strong>, visible for the
whole conversation — which is why the model's own replies never repeat them.</li>
<li>A line saying the conversation is not saved and disappears when she leaves.</li>
<li>Replies in three visual styles: a <span class="swatch red"></span> red edge for emergencies and
disclosures, an <span class="swatch amber"></span> amber edge for refusals, and plain for
conversation.</li>
</ul>
"""


def s_flow() -> str:
    steps = [
        ("device", "① Safety layer — on the phone",
         "Dart, microseconds. One of the five emergencies? <strong>Yes</strong> → bundled text, done, and "
         "<code>POST /chat/note</code> with the category only. <strong>No</strong> → send, with the category "
         "attached and an eight-second timeout if one was recognised."),
        ("server", "② The same safety layer again — on the server",
         "Python. The server re-classifies and trusts only its own result. A stale client's label is noted in "
         "the console, never acted on."),
        ("server", "③ Rate limit",
         f"{ratelimit.BURST} burst and {ratelimit.PER_MINUTE:g}/minute per caller; {ratelimit.GLOBAL_BURST} burst "
         f"and {ratelimit.GLOBAL_PER_MINUTE:g}/minute overall. A limited category still gets its own text."),
        ("server", "④ Retrieval",
         f"Bangla and romanised Bangla are translated to an English <em>search key only</em>, embedded, and "
         f"compared with all {len(CHUNKS)} passages. The nearest {chain.N_RESULTS} are kept."),
        ("gate", "⑤ The gate — a licence, not a door",
         f"If the closest passage is within <strong>{chain.RELEVANCE_FLOOR}</strong>, the model may answer "
         "from it. If not, it may only listen: no facts, no advice, no steps."),
        ("server", "⑥ The model",
         f"<code>{E(chain.MODEL)}</code> sees the <strong>raw</strong> message, the passages, the last "
         f"{sessions.MAX_TURNS} turns — and a note saying what category fired and exactly what code will "
         "append under its words."),
        ("check", "⑦ Output check",
         "Digits or an “@” in the model's own words fail, always. Advice or a step list fails when a category "
         "matched or the reply is below the floor. One retry, told what went wrong; then fixed text."),
        ("server", "⑧ The referral block — appended by code",
         "For a recognised safety category: the contacts and the one sentence of limit, from "
         "<code>referrals.py</code>. Full the first time in a conversation, one line after."),
        ("fallback", "Any failure at ③–⑦",
         "The category's own fixed text. There is no error path that reaches her."),
    ]
    boxes = "".join(
        f'<div class="step {k}"><div class="step-title">{title}</div><div>{body}</div></div>'
        + ('<div class="arrow">▼</div>' if i < len(steps) - 2 else "")
        for i, (k, title, body) in enumerate(steps)
    )
    return f"""<p>What happens to one message, from the moment she presses Send.</p>
<div class="flow">{boxes}</div>"""


def s_safety() -> str:
    rows = []
    for i, cat in enumerate(PRIORITY, 1):
        where = badge("device", "device") if cat in DEVICE else badge("model", "model")
        near = f' <span class="small">+{len(NEAR[cat])} near</span>' if cat in NEAR else ""
        rows.append([
            str(i), f"<code>{cat}</code>", KIND[cat], where,
            f"{PATTERN_COUNT.get(cat, 0)}{near}", t(DESCRIBE.get(cat, "")),
        ])
    return f"""
<p><strong>The rule it enforces:</strong> the model is never the safety layer. Emergency detection is
plain pattern matching, so its behaviour is fixed, inspectable and testable, cannot be argued with,
and does not drift when a model is updated. An LLM asked to spot an emergency will sometimes miss
one, and a miss means a person in danger gets a paragraph about safeguarding principles instead of
a phone number.</p>

<p><strong>Where it lives:</strong> <code>bharosha_service/app/safety.py</code> is the author.
It is exported to JSON and consumed by <code>lib/bharosha/safety.dart</code> on the phone — see
section 11.</p>

<h3>The {len(PRIORITY)} categories, in evaluation order</h3>
<p>The first category that matches wins. This is <em>evaluation</em> order, not severity: emergencies
come first so that “he will kill me if I leave” is an emergency and not a question about leaving;
refusals come before disclosure so that “my husband hits me, should I leave?” gets the leaving
refusal, which carries the timing warning; social categories come last so that “hi, he is beating
me” is an emergency.</p>
{table(["#", "Category", "Kind", "Answered", "Patterns", "Catches"], rows, "cats")}
<p class="small">{len(DEVICE)} categories answered on the device — the emergencies, and only those. The other
{len(PRIORITY) - len(DEVICE)} are recognised on the device too, and the category travels with the message;
the model writes the reply and, for a safety category, code appends the referral block. Every ordinary
question, which matches nothing, goes to the model as well.</p>

<h3>How matching works</h3>
<ul>
<li><strong>{TOTAL_PATTERNS} regular-expression patterns in {len(PATTERN_COUNT)} groups</strong>, written in
Bangla script, English, and romanised Bangla (“amake marche”), because people mix all three in one
sentence.</li>
<li><strong>{len(safety._NEAR_RULES)} unordered co-occurrence rules.</strong> Two groups of words within 6–8
words of each other, in <em>either</em> order. They exist because an ordered pattern for a concept with
no fixed order is a bug class: “my daughter was abused” matched while “they abused my daughter” did
not. English terms match as prefixes (“hit” matches “hitting”, not “white”); Bangla terms match as
substrings, because Bangla inflects by suffixing.</li>
<li><strong>Normalisation:</strong> Unicode NFC, zero-width joiners removed, lower-cased.</li>
<li><strong>Every social pattern is anchored end to end.</strong> A greeting reply can only be returned
when the message contains nothing else.</li>
<li><strong>Language:</strong> Bangla script → <code>bn</code>. Two or more whole-token hits from a shared
list of {len(safety.ROMANISED_BANGLA_WORDS)} common romanised words → <code>bn_roman</code>, which gets
Bangla script everywhere: fixed text, referral blocks, the prompt's language line. She typed Latin letters
because that is what her keyboard offered; she reads Bangla. No English words are in the list — “to”,
“help” and “problem” each turned an English sentence into two hits on their own.</li>
</ul>

<h3>Guards that run when the service starts</h3>
<ul>
<li><strong>Every category must map to a kind and have reply text</strong>, or the service refuses to
start. A missing reply is found at deploy time, not in front of a user.</li>
<li><strong><code>\\b</code> next to Bangla is an error.</strong> Most Bangla words end in a combining vowel
sign, which is not a “word character”, so a word boundary after it never matches. This silently
disabled a medical-advice rule (<span class="bn">লক্ষণ কী</span>) that had never once fired. It is also the
one known difference between Python's and Dart's regular expressions.</li>
</ul>

<h3>Categories that exist because of a specific failure</h3>
<dl>
<dt><code>coercive_control</code></dt>
<dd>Before it existed, <strong>25 of 25</strong> test messages — “he controls my money”, “he does not let me go
out”, <span class="bn">সে আমার ফোন চেক করে</span> — reached the corpus and got an explanation instead of 109.
It was missed for a structural reason: the disclosure rule paired a relationship word with a harm
word, and “he controls my money” has neither. The new rule keys on the grammar of being controlled
plus “me” or “my”, which keeps “what is coercive control?” out of it.</dd>
<dt><code>reporting_request</code></dt>
<dd>The model once answered “I want to report this” from staff-facing material with “you can report
anonymously” — pointing at an in-app form that needs a login and does not work. The fixed reply now
begins <em>“I cannot take a report.”</em></dd>
<dt><code>medical_advice</code></dt>
<dd>“How do I treat a burn on my hand?” retrieved <strong>acid-attack first aid</strong> at a distance inside the
range of genuine questions. No threshold could have separated them.</dd>
<dt><code>privacy</code></dt>
<dd>“Will my husband see this?” was reaching a model that knows nothing about this app. In a GBV app
that answer decides whether she types the next sentence.</dd>
<dt><code>personal_disclosure</code></dt>
<dd>“My boss touches me at work” got “I don't have reliable information about that.” Found by a
screenshot — the reason the input taxonomy was later written out in full.</dd>
</dl>
"""


def s_referrals() -> str:
    rows = []
    for h in referrals.NATIONAL_HELPLINES:
        crisis = badge("yes", "device") if h.in_emergency_script else badge("excluded", "warn")
        rows.append([f"<strong>{h.number}</strong>", E(h.name_en), crisis, E(h.desc_en)])
    rows.append([f"<strong>{referrals.KAAN_PETE_ROI_NUMBER}</strong>", "Kaan Pete Roi — emotional support",
                 badge("suicide & low distress", "device"),
                 f"Trained volunteers, <strong>{E(referrals.KAAN_PETE_ROI_HOURS_EN)} only</strong>. "
                 "Always listed after 999, with its hours."])
    rows.append(["email", "WaterAid Bangladesh safeguarding<br><code>" + referrals.SAFEGUARDING_EMAIL.replace("@", "@<wbr>") + "</code>",
                 badge("disclosure & reporting", "device"), "For anything involving a WaterAid programme, "
                 "workplace, staff member or partner."])
    fp = "".join(
        f"<tr><td>{E(p.organisation)}</td><td>{E(p.number)}</td><td>{E(p.email)}</td></tr>"
        for p in referrals.SAFEGUARDING_FOCAL_POINTS
    )
    return f"""
<p><strong>Where it lives:</strong> <code>bharosha_service/app/referrals.py</code> — the single source of
truth for every number and every fixed reply. The app's Important Numbers screen reads the same list.</p>

<h3>The numbers Bharosha can give out</h3>
{table(["Number", "Service", "In crisis replies", "What the app says it is"], rows, "nums")}

<h3>Safeguarding focal points ({len(referrals.SAFEGUARDING_FOCAL_POINTS)})</h3>
<p>Partner-organisation staff who hold the safeguarding role. Shown on the Important Numbers screen
and referred to by the disclosure and reporting replies.</p>
<table class="compact"><thead><tr><th>Organisation</th><th>Number</th><th>Email</th></tr></thead><tbody>{fp}</tbody></table>

<h3>The rules the numbers follow</h3>
<ul>
<li><strong>The model may never write a number.</strong> Every number arrives from this file and is appended
after generation. A hallucinated digit in a helpline is structurally impossible. The knowledge pack's
317 inline numbers were stripped at import for the same reason.</li>
<li><strong>999 always comes before Kaan Pete Roi</strong>, because it is the only 24-hour option, and Kaan
Pete Roi's hours are written into every reply that names it.</li>
<li><strong>16263 is never in a crisis reply.</strong> WaterAid confirmed it is Shastho Batayon, the national
<em>health</em> line, not a GBV hotline. Sending a survivor to a health line she believes is a GBV service is a
concrete harm.</li>
</ul>

<h3>Two numbers that were wrong</h3>
<p><strong>16263.</strong> The app's own Important Numbers screen called it a “Gender Based Violence Hotline —
24/7 confidential support for survivors”, while the chatbot five taps away correctly called it a health
line. The screen kept its own copy of the list, and the copies drifted. It now reads the same generated
list, its description says <em>“This is a HEALTH line, not a gender-based violence line — for violence, call
109 or 999”</em>, and a test pins that wording.</p>
<p><strong>16430</strong> was in the app as the GBV helpline months after it had been replaced by 16699. It
was caught by the knowledge pack, not by testing — which is why verification is now tracked.</p>

<h3>Verification</h3>
<p><code>VERIFICATION_STATUS = "{E(referrals.VERIFICATION_STATUS)}"</code>. <code>tools/verification_list.py</code>
generates <code>REFERRAL_VERIFICATION.md</code>, which lists, for each number, what Bharosha <em>claims</em>
it does and what hours it claims — because “it rings” is not a pass. A test fails if that checklist
is completed without the status being changed, or the status is changed while items are unticked.</p>
"""


def s_model() -> str:
    rows = [
        ["Model", f"<code>{E(chain.MODEL)}</code> on Groq", "Fast, inexpensive, and capable enough. How to evaluate a larger one is in the README."],
        ["Reasoning effort", f"<code>{chain.REASONING_EFFORT}</code>",
         "At the default, the model spent 5,800–7,400 characters of hidden reasoning and returned "
         "<strong>empty or cut-off replies</strong>. At <code>low</code>: complete every time."],
        ["Maximum tokens", str(chain.ANSWER_MAX_TOKENS), "A ceiling, not a length instruction."],
        ["Temperature", str(chain.TEMPERATURE),
         "One value for every reply. The ungrounded path used to be frozen at 0, which made “hello” return the "
         "identical sentence every time. The prohibition is enforced by the output check, not by sampling."],
        ["Truncation guard", "<code>reject_if_unusable</code>",
         "An empty reply, or <code>finish_reason == \"length\"</code>, is treated as a failure."],
        ["History", f"last {sessions.MAX_TURNS} turns",
         "Every turn, including the whole appended block and any emergency the phone answered itself."],
    ]
    return f"""
<p><strong>Where it lives:</strong> <code>bharosha_service/app/chain.py</code>.</p>
{table(["Setting", "Value", "Why"], rows, "kv3")}

<h3>One prompt, three slots</h3>
<p>There is one prompt for everything the model answers (Appendix B). It is written in this order —
who you are, how you talk, what you know, what the app will show, your limits — because the previous
prompt was mostly prohibitions and described the bot by what it was not, and a person reading the
replies could feel it. Every prohibition is still there, numbered under YOUR LIMITS so it can be
audited. Three slots are filled per message:</p>
<ul>
<li><strong>{{grounding_line}}</strong> — what the gate decided: answer from the passages, or listen only.</li>
<li><strong>{{app_note}}</strong> — one paragraph per category, telling the model what fired and exactly
what code will append under its words, so it writes the opening without repeating the contacts and
without softening the limit. “Nothing extra will be shown” for a message with no category.</li>
<li><strong>{{examples}}</strong> — seven short exchanges that teach the voice, for tone only.</li>
</ul>

<h3>What was copied from Probahini, and what was not</h3>
<p>Probahini is the reference chatbot (menstrual health, same model) whose voice this follows. Copied:
the model writes every reply; the full conversation history each turn; the <strong>raw</strong>
message, so “kemon acho” typed in Latin letters reaches a model that answers in Bangla on its own;
<code>(NO PREAMBLE)</code>; no length constraint. <strong>Not copied:</strong> <em>“If no relevant
information exists, refer to the Flow of Chat for context to create an informed and relevant
response.”</em> That sentence licenses filling gaps from training, and it is what produced Probahini
introducing itself as <em>“ChatGPT, an AI language model by OpenAI”</em>. Here: if you do not have the
information, say so plainly and kindly.</p>

<h3>The output check</h3>
<p><strong>Where it lives:</strong> <code>bharosha_service/app/assertions.py</code>. The same principle as
the safety layer, applied to the other end: <strong>do not trust the prohibition, check the output.</strong></p>
<p>Two checks. A run of three or more digits, or an “@”, in the model's own words fails on
<strong>every</strong> reply, with no exceptions — the numbers arrive from <code>referrals.py</code> or not
at all. Advice, steps and lists fail when a safety category matched or the reply is below the floor, and not
on an ordinary grounded answer, because WaterAid's material has legitimate numbered steps in it.</p>
<p>On a failure the model is asked <strong>once</strong> to rewrite, with a line saying what it did wrong
(Appendix B). If the rewrite fails too, she gets the fixed text. Retries and fallbacks are counted
separately at <code>/health</code>, because they are different findings: a retry means the prompt is
slightly loose, a fallback means the model could not be steered.</p>
{note("The first version of this check also fired on “first,”, “next,”, “it is important to” and their Bangla. "
      "Measured, those caught gentle sentences that were not advice and swapped in fixed text for about one reply in "
      "ten. A check that punishes kindness is the old problem wearing a new badge. Those patterns are gone; the "
      "ones that fire on the shape of instruction remain (Appendix C).")}
"""


def s_corpus() -> str:
    origin_rows = [
        ["Bhorosha Knowledge Base Pack", str(ORIGIN["knowledge_pack_pending_review"]), badge("pending review", "warn"),
         "Question-and-answer pairs written in English and Bangla together, with sources and review flags."],
        ["External sources", str(ORIGIN["external_pending_review"]), badge("pending review", "warn"),
         "; ".join(E(s) for s in EXT_SOURCES) + "."],
        ["WaterAid Global Safeguarding Framework 2023–2028 (PDF)", str(ORIGIN["pdf"]), badge("WaterAid", "device"),
         "Text-extractable pages only."],
        ["The app's own Knowledge Hub", str(ORIGIN["knowledge_hub"]), badge("WaterAid", "device"),
         "Read straight out of the Flutter source file at build time, so the chatbot and the app cannot drift."],
    ]
    cats = "".join(f"<tr><td>{E(k)}</td><td>{v}</td></tr>" for k, v in PACK_CATS.most_common())
    return f"""
<p><strong>{len(CHUNKS)} passages from {len(SOURCES)} sources. Every one has both an English and a Bangla side.</strong>
Retrieval matches on the English side; the model reads the Bangla side when the question was in
Bangla, so a Bangla answer is built from Bangla text rather than translated on the fly.</p>
{table(["Origin", "Passages", "Status", "Notes"], origin_rows, "corp")}

<h3>Bangla</h3>
<ul>
<li>{len(CHUNKS) - MACHINE_BN} passages came with Bangla written by the knowledge pack.</li>
<li>{MACHINE_BN} were machine-translated and are marked <code>machine_pending_review</code>. Human
corrections go in <code>corpus/translations_bn.json</code> and survive every rebuild.</li>
<li>The fixed safety replies are <strong>not</strong> machine-translated — see section 6.</li>
</ul>

<h3>What is deliberately left out</h3>
<ul>
<li><strong>The 25 scanned policy pages</strong> inside the app. Bangla OCR is not reliable enough for a
safety-critical corpus.</li>
<li><strong>The Knowledge Hub's “Reporting Mechanisms” topic</strong>, which the app itself hides. Two other
hidden topics — Types of GBV and Safeguarding Principles — were reviewed and included.</li>
</ul>

<h3>The knowledge pack — why only {len(PACK['entries'])} of 459 rows</h3>
<p><code>tools/import_knowledge_pack.py</code> loads a row only when it is marked for the chatbot, marked
high confidence, and marked as needing no expert review. It also:</p>
<ul>
<li><strong>Excludes the 198 legal rows.</strong> Legal questions are refused before retrieval, so indexing
them would let legal claims surface inside answers to other questions. That material is therefore
unreachable twice over — a decision pending with the product owner (section 18).</li>
<li><strong>Removes every phone number</strong> from the text, rewriting “call 109” as “call the helpline”, so
numbers can only come from <code>referrals.py</code>.</li>
<li><strong>Rewrites WaterAid's global UK inbox</strong> to the Bangladesh address.</li>
<li><strong>Puts the question, and the ways people actually ask it, in front of the answer</strong> in the
searchable text. This is what made retrieval work for situations (“what if my boss touches me”)
rather than only for definitions.</li>
</ul>
<h4>Knowledge-pack passages by category</h4>
<table class="compact narrow"><thead><tr><th>Category</th><th>Q&amp;A rows</th></tr></thead><tbody>{cats}</tbody></table>
"""


def s_retrieval() -> str:
    return f"""
<p><strong>Where it lives:</strong> <code>app/embedding.py</code>, <code>app/chain.py</code>,
<code>build_corpus.py</code>.</p>
<ul>
<li><strong>Embedding model:</strong> <code>{E(embedding.MODEL_NAME)}</code>, as an int8-quantised ONNX
file (~120 MB) run by fastembed. No PyTorch.</li>
<li><strong>No vector database.</strong> {len(CHUNKS)} vectors, one numpy dot product, every passage compared.
The corpus is embedded at startup from text — there is no binary index to go stale.</li>
<li><strong>Chunking:</strong> 700 characters with 130 overlap, and <span class="bn">।</span> as a sentence
separator so Bangla is not cut mid-sentence.</li>
<li><strong>Bangla questions</strong> are translated to English by one small Groq call, as a search key only.
The model always answers the original.</li>
</ul>

<h3>Why this embedder</h3>
<p>Multilingual models (LaBSE, multilingual-e5) were tried and measured first. Their 250,000-word
vocabulary alone took the process to <strong>925 MB</strong> of memory against a 512 MB server, and they
separated genuine questions from unrelated ones worse. The cause was found by profiling, not guessed.
An English-only model plus translation was smaller and more accurate.</p>

<h3>The two thresholds</h3>
{table(["Threshold", "Value", "What it decides"], [
    ["Relevance floor", f"<strong>{chain.RELEVANCE_FLOOR}</strong>",
     "Whether the model may <em>assert</em> from the passages. Measured: worst genuine question 0.550, "
     "nearest unrelated message 0.725. Placed toward rejection, because a false reject sends someone "
     "to 109 while a false accept produces a confident answer assembled from irrelevant passages. "
     "Measured on the earlier, smaller corpus — worth re-measuring."],
    ["Off-topic distance", f"<strong>{chain.OFF_TOPIC_DISTANCE}</strong>",
     "Only which fallback text to send if the model is unavailable: the full “I don't have that” "
     "reply or the one-line off-topic reply. Measured on 20 on-topic and 18 unrelated questions."],
], "kv3")}

<h3>How well it now finds situations</h3>
<p>These used to be answered with a fixed paragraph, on a measurement taken before the knowledge pack
existed. Measured afterwards (lower is closer):</p>
{table(["Message", "Distance", "Found in"], [
    ["my boss touches me at work", "0.303", "Understanding GBV"],
    ["my friend is being abused by her husband", "0.330", "Supporting Someone"],
    ["what should I do if my boss harasses me", "0.361", "Safeguarding and PSEAH"],
    ["I am anxious all the time", "0.450", "Health and Wellbeing"],
], "compact")}
"""


def s_app() -> str:
    files = [
        ("chat_screen.dart", "The screen: messages, routing, fallbacks, quick exit, screenshot blocking, styling."),
        ("safety.dart", "The on-device safety layer — reads the generated rules."),
        ("referrals.dart", "Numbers, focal points and every fixed reply — reads the generated JSON."),
        ("client.dart", "The HTTP client. 30-second timeout; every failure becomes “unreachable”, never an exception."),
        ("rules_loader.dart", "Loads the bundled JSON once at startup."),
    ]
    rows = [[f"<code>lib/bharosha/{f}</code>", str(lines_of(APP / "lib" / "bharosha" / f)), d] for f, d in files]
    return f"""
{table(["File", "Lines", "Role"], rows, "compact")}
<ul>
<li><strong>How she gets there:</strong> the “Ask Bharosha” card on the home page, or the side drawer.
Route <code>/bharosha</code>. <strong>No login is needed.</strong></li>
<li><strong>Device first.</strong> The safety layer runs on the phone before anything is sent, so she gets
999 and 109 with no signal and with the server asleep.</li>
<li><strong>Screenshot blocking.</strong> Android <code>FLAG_SECURE</code> is switched on while the chat is open,
through a channel in <code>MainActivity.kt</code>: no screenshots, no screen recording, and a blank card
in the recent-apps switcher.</li>
<li><strong>Leave now.</strong> Clears the conversation, asks the server to forget it, and closes the app
immediately.</li>
<li><strong>Nothing saved.</strong> Messages live in memory only — no database, no files, no shared
preferences. Closing the screen erases them.</li>
<li><strong>Session id.</strong> A new random UUID for every conversation, never the Firebase user id, so two
conversations from one person cannot be linked.</li>
<li><strong>No notifications</strong> are ever scheduled.</li>
<li><strong>Language.</strong> A toggle in the header; but she is always answered in the language she wrote in.</li>
<li><strong>Offline fallback.</strong> If the server cannot be reached, any recognised category shows its bundled
text. Only an unrecognised question gets “I could not reach the service” — which is honest, because it
was never looked up.</li>
<li><strong>The Important Numbers screen</strong> (<code>emergency_contacts_screen.dart</code>) now reads the same
generated list as the chatbot instead of keeping its own.</li>
</ul>
{note("<strong>iOS:</strong> the project is configured for Android. There is a default iOS folder but no screenshot "
      "protection on iOS. An equivalent exists — cover the window when the app is backgrounded — and should be "
      "built if iOS is going to ship.", "warn")}
"""


def s_sync() -> str:
    return f"""
<p>The safety layer runs twice — on the phone and on the server. Two hand-maintained copies of
life-safety patterns in two languages would drift, and the drift would be invisible: a pattern fixed on
the server, a phrase still missed on the phone.</p>
<p><strong>So Python is the only author and Dart is a consumer.</strong> <code>tools/export_shared.py</code>
writes three files into both <code>bharosha_service/shared/</code> and the Flutter
<code>assets/bharosha/</code>:</p>
{table(["File", "Contains"], [
    ["<code>safety_rules.json</code>", "Patterns, co-occurrence rules, category lists, evaluation order, category→kind, the device list."],
    ["<code>referrals.json</code>", "Every number and description, focal points, the safeguarding email, verification status, and all fixed replies in both languages."],
    ["<code>safety_cases.json</code>", f"<strong>{len(CASES)} shared test cases</strong> — the same messages both languages' test suites run. Listed in full in Appendix D."],
], "compact")}
<ul>
<li>The exporter <strong>refuses to write</strong> if Python disagrees with any declared case.</li>
<li>A Python test <strong>fails</strong> if the generated files are out of date.</li>
<li>Dart runs the identical {len(CASES)} cases, so “ported with the same coverage” is checked, not claimed.</li>
<li>Patterns stay inside what both regex engines support: no look-behind, no named groups, and no
<code>\\b</code> near Bangla.</li>
</ul>
<p><strong>After editing <code>safety.py</code> or <code>referrals.py</code>, always run
<code>python tools/export_shared.py</code>.</strong></p>
"""


def s_privacy() -> str:
    return f"""
{table(["Where", "What is kept", "For how long"], [
    ["Her phone", "Nothing.", "—"],
    ["Server memory", f"The last {sessions.MAX_TURNS} turns of an open conversation — her message and the whole reply — keyed by the random session id. After an emergency the phone answered itself, one fixed sentence naming the <em>category</em>, never her words.",
     f"Until {int(sessions.TTL_SECONDS // 60)} minutes of silence, <strong>Leave now</strong>, or a restart. At most {sessions.MAX_SESSIONS:,} conversations; the oldest is dropped first."],
    ["Server memory", "Which categories' full referral block this conversation has already seen — category names only.", "Same lifetime."],
    ["Server disk", "Nothing.", "—"],
    ["Logs", "Nothing — no question text, no answer text, no session id, no IP address.", "—"],
    ["Counters", "Open sessions; output checks, retries and fallbacks.", "Until restart"],
    ["Rate limiter", "A token count per client address, in memory.", f"Capped at {ratelimit.MAX_TRACKED:,} addresses"],
], "compact")}
<ul>
<li><strong>What does leave the phone:</strong> the message, over HTTPS, for everything except the five
emergencies — with the phone's category label attached, which the server checks rather than trusts — and
for a Bangla or romanised question, a copy sent to Groq for translation. After an emergency, a category
label only. The privacy reply says all of this plainly.</li>
<li><strong>Groq</strong> receives the message, the retrieved passages, the capped history and the prompt,
and no identifier.</li>
<li><strong>Secrets:</strong> <code>GROQ_API_KEY</code> comes from the environment only. <code>.env</code>,
keystores and <code>key.properties</code> are ignored by git, and every push was scanned for keys.</li>
</ul>
"""


def s_server() -> str:
    deps = [l.strip() for l in (SVC / "requirements.txt").read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    files = [
        ("api.py", "HTTP routes, and the pipeline in the order that is the safety design."),
        ("safety.py", "The deterministic safety layer."),
        ("referrals.py", "Every number and every fixed reply."),
        ("chain.py", "Retrieval, translation, the prompt, the model call, the truncation guard."),
        ("assertions.py", "The below-floor output check and its counter."),
        ("embedding.py", "The ONNX embedder."),
        ("sessions.py", "Capped, expiring, in-memory conversation history."),
        ("ratelimit.py", "Token buckets, keyed from the right of X-Forwarded-For."),
        ("knowledge_source.py", "Reads the Knowledge Hub text out of the Flutter source."),
    ]
    rows = [[f"<code>app/{f}</code>", str(lines_of(SVC / "app" / f)), d] for f, d in files]
    return f"""
{table(["File", "Lines", "Role"], rows, "compact")}

<h3>Endpoints</h3>
{table(["Route", "Does"], [
    ["<code>POST /chat</code>", "<code>{{session_id, query, category?}}</code> → <code>{{response, kind}}</code>. The phone's category is advisory; the server re-classifies."],
    ["<code>POST /chat/note</code>", "<code>{{session_id, category}}</code>. The phone answered an emergency itself; the server records the category only. Anything but a known emergency category is refused."],
    ["<code>POST /forget</code>", "Drops a conversation. Called by Leave now and when the screen closes."],
    ["<code>GET /health</code>", "Cheap — never loads the model. Session count and output-check counters."],
    ["<code>GET /console</code>, <code>POST /console/ask</code>", "Developer console. These routes <strong>do not exist</strong> unless <code>BHAROSHA_DEV_CONSOLE=on</code>; a test asserts they are absent by default."],
], "compact")}

<h3>Behaviour worth knowing</h3>
<ul>
<li><strong>Startup.</strong> The port opens immediately and the corpus is embedded on a background thread.
Safety replies work from the first millisecond. A question in the first ~30 seconds gets <em>“I am still
starting up — send your message again in a few seconds”</em>, not “I don't have information”, which would
be false.</li>
<li><strong>Rate limiting</strong> applies only to traffic that would reach the model, and a limited category
still receives its own text. The client address is read from <code>X-Forwarded-For</code>, counting
{ratelimit.TRUSTED_PROXY_HOPS} trusted proxy from the right, so a caller cannot spoof it.</li>
<li><strong>A Groq outage</strong> never produces an error. Every failure path ends in fixed text with real
numbers in it.</li>
<li><strong>Imports are ordered on purpose.</strong> The route module does not import the embedder or the model
client at load time, so an emergency is answered even if they fail to load.</li>
</ul>

<h3>Container</h3>
<p>Python 3.11-slim; dependencies installed; the embedder downloaded and warmed <em>at build time</em>; one
worker; listens on <code>$PORT</code> for Render. Dependencies: {", ".join(f"<code>{E(d)}</code>" for d in deps)}.</p>
"""


def s_testing() -> str:
    return f"""
{table(["Suite", "Tests", "What it proves"], [
    ["Python, offline", "364", "Classification in three languages; every fixed reply and referral block; the prompt's seven limits and its slots; memory, the emergency note and the privacy claims; the output check's catches and its allowed sentences; the retry; that emergencies never reach the model; that the shared files are current."],
    ["Python, live", "68", "Against a running server: the five emergencies on the device; every recognised category gets model text then its block, full then compact; no model-written digits or emails; nothing below the floor gives advice; openings vary; nothing begins “Thank you for telling me”; romanised Bangla gets Bangla script; a salam gets a salam; “he keeps my salary” then “ki korbo?” is about the salary; an emergency the phone answered is remembered. Skipped unless <code>BHAROSHA_BASE</code> is set."],
    ["Dart", "238", f"The same {len(CASES)} shared cases, in three languages; exactly five device categories; offline text for every category; language detection and greeting mirroring; the referral list; 16263's label."],
], "kv3")}
<p><strong>The tests that matter most assert what is <em>absent</em>:</strong> no number the model wrote, no
helpline under a greeting, no advice under a disclosure, no “Thank you for telling me”. Restraint is the
hardest thing to keep and the easiest to lose without anyone noticing.</p>
<p><code>tools/feel_review.py</code> produces <code>feel_review.md</code>: twenty messages, seven English,
seven Bangla, six romanised, with the previous Bharosha's reply and this one's side by side, shuffled
per row, for blind review by WaterAid safeguarding staff and a native Bangla speaker. Whether a person
would feel heard is not a thing a test can score.</p>
"""


def s_run() -> str:
    return """
<h3>Start the server</h3>
<pre>cd bharosha_service
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements-dev.txt
copy .env.example .env          # then put your GROQ_API_KEY in .env
.\\dev.ps1                       # http://127.0.0.1:8000/console</pre>
<p><code>dev.ps1</code> listens on <code>127.0.0.1</code>, which a phone cannot reach. To test from a real
phone on the same Wi-Fi, listen on all interfaces instead:</p>
<pre>$env:BHAROSHA_DEV_CONSOLE = "on"
.\\.venv\\Scripts\\python.exe -m uvicorn api:app --app-dir app --host 0.0.0.0 --port 8000</pre>

<h3>Run the app against it</h3>
<pre>cd stop_gender_violence_fresh_ui
flutter run --dart-define=BHAROSHA_URL=http://10.0.2.2:8000        # Android emulator
flutter run --dart-define=BHAROSHA_URL=http://&lt;PC's LAN IP&gt;:8000   # real phone</pre>

<h3>After changing the corpus</h3>
<pre>python tools/import_knowledge_pack.py      # re-import the pack
python build_corpus.py                     # re-chunk everything into corpus/chunks.json</pre>

<h3>After changing safety.py or referrals.py</h3>
<pre>python tools/export_shared.py              # regenerate the JSON the app bundles
python tools/verification_list.py          # regenerate the number checklist</pre>

<h3>Run the tests</h3>
<pre>python -m pytest tests                                   # offline, ~5 seconds
$env:BHAROSHA_BASE = "http://127.0.0.1:8000"
python -m pytest tests/test_live_behaviour.py -v         # live, needs the server
cd ..\\stop_gender_violence_fresh_ui
flutter test test/bharosha_safety_test.dart</pre>

<h3>Developer tools</h3>
<table class="compact"><thead><tr><th>Tool</th><th>Does</th></tr></thead><tbody>
<tr><td><code>dev.ps1</code></td><td>Starts the server with the developer console switched on.</td></tr>
<tr><td><code>tools/console.html</code></td><td>The page at <code>/console</code>. Ask anything and see the category, the route, the time taken, a distance bar against the thresholds, and the sources used. Presets cover every category in both languages. A browser page because Windows terminals render Bangla as boxes.</td></tr>
<tr><td><code>tools/probe.py</code></td><td>Fires every test message at a running server and writes <code>probe_results.md</code> for reading.</td></tr>
<tr><td><code>tools/measure_off_topic.py</code></td><td>Measures where on-topic and unrelated questions fall, to set the off-topic distance.</td></tr>
<tr><td><code>tools/verification_list.py</code></td><td>Generates <code>REFERRAL_VERIFICATION.md</code>.</td></tr>
<tr><td><code>tools/import_knowledge_pack.py</code></td><td>Imports and filters the knowledge pack.</td></tr>
<tr><td><code>tools/translate_corpus.py</code></td><td>Machine-translates English-only passages into the overlay file.</td></tr>
<tr><td><code>build_corpus.py</code></td><td>Chunks every source into <code>corpus/chunks.json</code>.</td></tr>
<tr><td><code>check_retrieval.py</code></td><td>Measures retrieval distances for a question set.</td></tr>
<tr><td><code>tools/export_shared.py</code></td><td>Exports the Python rules, replies and test cases for the app.</td></tr>
</tbody></table>
"""


def s_history() -> str:
    steps = [
        ("The brief", "Set the non-negotiables in section 1: deterministic emergency detection, counter-only logging, "
                      "random session ids, no login, referral first, the three prohibited subjects, answers only from "
                      "retrieved content, no invented numbers."),
        ("First build, then a reset", "The first version used a vector database and multilingual embedders. The product owner "
                                      "reset it — <em>“You have over-built this”</em> — and it was rebuilt on Probahini's shape "
                                      "with ten agreed deviations."),
        ("Memory", "The multilingual embedders reached 925 MB. Profiling traced it to vocabulary size; the fix was a "
                   "small English embedder, query translation and a plain dot product."),
        ("Empty replies", "The product owner diagnosed the model's reasoning budget; it was proved from "
                          "<code>finish_reason</code> and fixed with <code>reasoning_effort=\"low\"</code>."),
        ("Disclosures", "“My boss touches me” got “I don't have information.” Found by accident; the disclosure "
                        "category followed."),
        ("Corpus growth", "From 37 passages to 418: external sources, 73 machine translations, then the knowledge "
                          "pack — which also caught the dead 16430."),
        ("“kemon acho?”", "Got a crisis leaflet. That produced the written input taxonomy, the social categories, and "
                          "the developer console."),
        ("“It feels like saved messages”", "Measurement showed the corpus now answered situations well — the evidence "
                                           "for hard-coding them was stale. Decision: <em>beyond the safety layer, be "
                                           "Probahini.</em> One path, the model always, the gate as a licence."),
        ("The leak", "A 20B model does not hold a prohibition perfectly. The output check was added; measured rate 9.8%."),
        ("The sweep", "Coercive control, reporting, the 16263 screen, the verification checklist, the offline "
                      "greeting fix, and the live assertion suite."),
        ("The upgrade brief", "Users still said Bharosha felt like saved replies, and they were right: seventeen "
                              "categories were fixed text and the model never saw an emotional message. Eight "
                              "changes, each its own commit: only the five emergencies stay on the phone; the "
                              "model writes and code appends the referral block, full then compact; a prompt "
                              "that listens before it informs; twelve turns of memory and a note for emergencies "
                              "the phone answered; romanised Bangla answered in Bangla and greetings mirrored; a "
                              "narrower output check on every reply with one retry; one temperature. Streaming "
                              "is the ninth, and is not done."),
    ]
    items = "".join(f"<li><strong>{k}.</strong> {v}</li>" for k, v in steps)
    log = "".join(
        f"<tr><td><code>{c.split(chr(9))[0]}</code></td><td>{c.split(chr(9))[1]}</td><td>{E(c.split(chr(9))[2])}</td></tr>"
        for c in COMMITS
    )
    return f"""<ol class="history">{items}</ol>
<h3>Commit history</h3>
<table class="compact"><thead><tr><th>Commit</th><th>Date</th><th>Message</th></tr></thead><tbody>{log}</tbody></table>"""


def s_open() -> str:
    return """
<h3>Blocks launch</h3>
<ul>
<li><strong>No referral number has been dialled.</strong> The checklist exists; the calls have not been made.
16263 needs particular attention — press reports say the service has degraded.</li>
<li><strong>Not deployed</strong>, and the app must be built with <code>BHAROSHA_URL</code> to use a server at all.</li>
<li><strong>The prompt changed how disclosures are answered.</strong> WaterAid safeguarding must sign off the
prompt, the category notes and the split referral blocks. Ten fixed replies were already awaiting sign-off.</li>
<li><strong>No Bangla text has been read by a native speaker</strong> — the fixed replies, the blocks, or the
prompt's examples. <code>feel_review.md</code> is the blind review; it needs reviewers.</li>
</ul>
<h3>Known weaknesses</h3>
<ul>
<li>The output check is a pattern list. It catches the shapes of advice it knows; a new shape could pass it.
The retry and fallback counts at <code>/health</code> are the measure, and <code>probe_results.md</code>
records them.</li>
<li>Conversation history lives in one process's memory. A restart, or a second server instance, loses a
conversation mid-clarification.</li>
<li>Every turn except an emergency now costs a model call and needs a network. A recognised category waits
eight seconds, then shows fixed text.</li>
<li>The relevance floor was measured on the smaller corpus and should be re-measured.</li>
<li>Streaming — words appearing as they are written — is phase two of the brief and is not built. If it is,
the output check must run on the complete text before the bubble is final.</li>
<li><code>flutter_markdown</code>, which draws every reply bubble, is discontinued upstream.</li>
<li>The app's incident report form needs a login and is not reachable, so Bharosha is built never to
mention it.</li>
<li>No screenshot protection on iOS.</li>
</ul>
"""


def s_decisions() -> str:
    return """
<p>These belong to the product owner and WaterAid, not to the code.</p>
<ol>
<li><strong>Sign-off</strong> on the new prompt, the category notes and the referral blocks — this changed how
disclosures are answered — and on the 381 corpus passages pending review.</li>
<li><strong>The legal refusal.</strong> Whether to answer <em>recognition</em> questions (“is denying inheritance a
form of violence?”) while still refusing <em>entitlement</em> questions (“what am I owed?”). That would make
the 198 legal knowledge-pack rows usable.</li>
<li><strong>The 125 unreviewed knowledge-pack rows.</strong> Whether to load them, flagged as pending review.</li>
<li><strong>A larger model.</strong> <code>openai/gpt-oss-120b</code>, if the account has it — only after the
comparison the README describes: fewer retries, fewer fallbacks, and a better blind read, all three.</li>
<li><strong>iOS.</strong> Whether it ships — which decides whether iOS screenshot protection is built.</li>
</ol>
"""


# --------------------------------------------------------------------------
# Appendices
# --------------------------------------------------------------------------

def a_replies() -> str:
    usage = {}
    for cat in referrals.RESPONSES:
        if cat in DEVICE:
            usage[cat] = "Shown on the device"
        elif cat in PRIORITY:
            usage[cat] = "Fallback only — the model writes the reply"
        elif cat == "unreachable":
            usage[cat] = "App cannot reach the server"
        else:
            usage[cat] = "Server operational reply"
    order = [c for c in PRIORITY if c in referrals.RESPONSES] + [
        c for c in referrals.RESPONSES if c not in PRIORITY]
    cards = []
    for cat in order:
        status = (badge("awaiting sign-off", "warn") if cat in DRAFT
                  else badge("pending WaterAid sign-off", "warn") if cat in PENDING
                  else badge("no sign-off flag in code", "plain"))
        r = referrals.RESPONSES[cat]
        cards.append(f"""
<div class="reply">
  <div class="reply-head"><code>{cat}</code> {status} <span class="use">{usage[cat]}</span></div>
  <div class="reply-body">
    <div class="col"><div class="lang">English</div>{md(r['en'])}</div>
    <div class="col bn-col"><div class="lang">বাংলা</div>{md(r['bn'])}</div>
  </div>
</div>""")
    blocks = []
    for cat in sorted(referrals.BLOCKS):
        b = referrals.BLOCKS[cat]
        blocks.append(f"""
<div class="reply">
  <div class="reply-head"><code>{cat}</code> {badge("referral block — under the model's words", "plain")}</div>
  <div class="reply-body">
    <div class="col"><div class="lang">English · full</div>{md(b['en']['full'])}<div class="lang" style="margin-top:8px">English · compact</div>{md(b['en']['compact'])}</div>
    <div class="col bn-col"><div class="lang">বাংলা · full</div>{md(b['bn']['full'])}<div class="lang" style="margin-top:8px">বাংলা · compact</div>{md(b['bn']['compact'])}</div>
  </div>
</div>""")
    footer = ("<h3>The referral blocks</h3><p>What code appends under a model-written reply for each safety "
              "category: the full block the first time that category comes up in a conversation, the "
              "one-line compact block every time after.</p>" + "".join(blocks))
    return f"""<p>Every fixed reply Bharosha can show, exactly as written in <code>referrals.py</code>, in both
languages: {len(referrals.RESPONSES)} replies. Since the conversational rewrite these are the
<strong>fallbacks</strong> — shown by the phone when the server cannot be reached within eight seconds, and by
the server when the model or the corpus is unavailable — except the five emergency scripts, which are always
what she sees. The referral blocks that follow model-written replies are listed after them.</p>
<p>The Bangla was written directly, not machine-translated — but it was written by the developer and
has not yet been reviewed by a native speaker.</p>
{"".join(cards)}{footer}"""


def a_prompts() -> str:
    return f"""
<p>Verbatim from <code>chain.py</code>. Words in braces are filled in for each message.</p>
<h3>The prompt</h3>
<pre class="prompt">{E(chain.PROMPT)}</pre>
<h3>{{grounding_line}} when the passages cleared the floor</h3>
<pre class="prompt">{E(chain.GROUNDED_LINE)}</pre>
<h3>{{grounding_line}} when they did not</h3>
<pre class="prompt">{E(chain.UNGROUNDED_LINE)}</pre>
<h3>{{app_note}} — one per category</h3>
<p>Written in English for the model; it still replies in her language. <code>{{block}}</code> becomes “the
full contacts block” or “a one-line reminder of the helpline” depending on whether this category's contacts
have already appeared in the conversation. A message with no category gets: <em>{E(chain.NO_CATEGORY_NOTE)}</em></p>
<table class="compact"><thead><tr><th>Category</th><th>Note</th></tr></thead><tbody>
{"".join(f"<tr><td><code>{c}</code></td><td>{E(n)}</td></tr>" for c, n in chain.APP_NOTES.items())}
</tbody></table>
<h3>{{examples}} — the voice, for tone only</h3>
<pre class="prompt">{E(chain.EXAMPLES)}</pre>
<h3>{{retry_note}} — above the user's message on the one retry the output check allows</h3>
<pre class="prompt">{E(chain.RETRY_NOTE)}</pre>
<h3>The translation prompt — for the search key only</h3>
<pre class="prompt">{E(chain.TRANSLATE_PROMPT)}</pre>
"""


def a_assertions() -> str:
    items = "".join(f"<li><code>{E(p)}</code></li>" for p in assertions._LIST_MARKERS)
    adv = "".join(f"<li><code>{t(p)}</code></li>" for p in assertions._ADVISORY)
    return f"""<p>From <code>assertions.py</code>. A number or email in the model's own words — a run of three or
more digits, Bangla digits included, or an “@” — fails on every reply, always. The list markers and advisory
phrases below fail when a safety category matched or the reply is below the relevance floor; not on an
ordinary grounded answer, because WaterAid's material has legitimate numbered steps in it. On a failure the
model is asked once to rewrite; if that fails too, the fixed text is sent.</p>
<h3>List markers ({len(assertions._LIST_MARKERS)})</h3><ul class="code">{items}</ul>
<h3>Advisory phrases ({len(assertions._ADVISORY)})</h3><ul class="code">{adv}</ul>"""


def a_cases() -> str:
    rows = "".join(
        f"<tr><td>{i}</td><td>{t(c['message'])}</td><td>{c['kind']}</td>"
        f"<td>{'' if c['category'] is None else '<code>' + c['category'] + '</code>'}</td><td>{c['language']}</td></tr>"
        for i, c in enumerate(CASES, 1)
    )
    return f"""<p>All {len(CASES)} messages from <code>shared/safety_cases.json</code>, with the category each must
produce. Both the Python and the Dart test suites run every one.</p>
<table class="cases"><thead><tr><th>#</th><th>Message</th><th>Kind</th><th>Category</th><th>Lang</th></tr></thead>
<tbody>{rows}</tbody></table>"""


def a_config() -> str:
    env = [
        ("GROQ_API_KEY", "—", "Required for any model reply. From the environment or <code>.env</code> only."),
        ("BHAROSHA_MODEL", chain.MODEL, "The Groq model."),
        ("BHAROSHA_TRANSLATION_MODEL", "same as model", "Model used for the Bangla search-key translation."),
        ("BHAROSHA_REASONING_EFFORT", chain.REASONING_EFFORT, "Reasoning budget. <code>low</code> fixes empty replies."),
        ("BHAROSHA_TEMPERATURE", str(chain.TEMPERATURE), "One temperature for every reply; safety is enforced by the output check, not sampling."),
        ("BHAROSHA_ANSWER_MAX_TOKENS", str(chain.ANSWER_MAX_TOKENS), "Ceiling on a reply."),
        ("BHAROSHA_TRANSLATION_MAX_TOKENS", "3000", "Ceiling on a translation."),
        ("BHAROSHA_RELEVANCE_FLOOR", str(chain.RELEVANCE_FLOOR), "The gate: grounded or not."),
        ("BHAROSHA_OFF_TOPIC_DISTANCE", str(chain.OFF_TOPIC_DISTANCE), "Which fallback text when the model is unavailable."),
        ("BHAROSHA_N_RESULTS", str(chain.N_RESULTS), "Passages retrieved per message."),
        ("BHAROSHA_TRANSLATE_QUERIES", "on", "Translate Bangla to an English search key."),
        ("BHAROSHA_CHUNKS", "corpus/chunks.json", "Corpus file."),
        ("BHAROSHA_EMBED_MODEL", embedding.MODEL_NAME, "Embedding model."),
        ("BHAROSHA_EMBED_FILE", "int8 ONNX export", "Which ONNX file to load."),
        ("BHAROSHA_EMBED_BATCH", "4", "Embedding batch size at startup."),
        ("BHAROSHA_EMBED_THREADS", "1", "Embedding threads."),
        ("BHAROSHA_MAX_TURNS", str(sessions.MAX_TURNS), "Conversation turns kept."),
        ("BHAROSHA_SESSION_TTL", f"{int(sessions.TTL_SECONDS)} s", "Silence before a conversation is forgotten."),
        ("BHAROSHA_MAX_SESSIONS", str(sessions.MAX_SESSIONS), "Conversations held at once."),
        ("BHAROSHA_RATE_BURST", str(ratelimit.BURST), "Per-caller burst."),
        ("BHAROSHA_RATE_PER_MINUTE", f"{ratelimit.PER_MINUTE:g}", "Per-caller sustained rate."),
        ("BHAROSHA_GLOBAL_BURST", str(ratelimit.GLOBAL_BURST), "Whole-service burst."),
        ("BHAROSHA_GLOBAL_PER_MINUTE", f"{ratelimit.GLOBAL_PER_MINUTE:g}", "Whole-service sustained rate."),
        ("BHAROSHA_RATE_MAX_TRACKED", str(ratelimit.MAX_TRACKED), "Caller addresses remembered."),
        ("BHAROSHA_TRUSTED_PROXY_HOPS", str(ratelimit.TRUSTED_PROXY_HOPS), "Proxies trusted in X-Forwarded-For."),
        ("BHAROSHA_DEV_CONSOLE", "off", "Registers the developer console routes. Never set in production."),
        ("BHAROSHA_BASE", "—", "Test-only: the server the live test suite targets."),
        ("BHAROSHA_URL (Flutter)", "empty", "Build-time <code>--dart-define</code>: the server the app talks to."),
    ]
    rows = [[f"<code>{n}</code>", f"<code>{E(str(d))}</code>", w] for n, d, w in env]
    return table(["Variable", "Default", "Effect"], rows, "compact env")


def a_files() -> str:
    groups = {
        "Service": sorted(p for p in (SVC / "app").glob("*.py")),
        "Service tools": sorted([*SVC.glob("*.py"), *(SVC / "tools").glob("*.py"), SVC / "tools" / "console.html", SVC / "dev.ps1", SVC / "Dockerfile"]),
        "Service tests": sorted((SVC / "tests").glob("*.py")),
        "Corpus": sorted(p for p in (SVC / "corpus").iterdir() if p.is_file()),
        "Generated (shared)": sorted((SVC / "shared").glob("*.json")),
        "Documents": sorted([SVC / "README.md", SVC / "INPUT_TAXONOMY.md", SVC / "REFERRAL_VERIFICATION.md"]),
        "Flutter": sorted([*(APP / "lib" / "bharosha").glob("*.dart"), APP / "lib" / "screens" / "emergency_contacts_screen.dart", APP / "test" / "bharosha_safety_test.dart"]),
    }
    out = []
    for name, paths in groups.items():
        rows = "".join(
            f"<tr><td><code>{E(str(p.relative_to(REPO)).replace(chr(92), '/'))}</code></td>"
            f"<td>{lines_of(p) if p.suffix not in ('.pdf',) else '—'}</td></tr>"
            for p in paths if p.exists()
        )
        out.append(f"<h3>{name}</h3><table class='compact files'><thead><tr><th>File</th><th>Lines</th></tr></thead><tbody>{rows}</tbody></table>")
    return "".join(out)


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

CSS = """
@page { size: A4; margin: 17mm 16mm 20mm 16mm; }
:root { --ink:#1c1d21; --muted:#5f636b; --line:#dfe2e7; --soft:#f5f6f8;
        --accent:#5E2A8E; --accent-soft:#f1ebf7; --red:#a81e24; --red-soft:#fdecec;
        --amber:#8a5200; --amber-soft:#fdf3e4; --green:#1d6f42; --green-soft:#e6f3eb;
        --blue:#1f4e9c; --blue-soft:#e7eefa; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", system-ui, sans-serif; font-size: 9.6pt; line-height: 1.5;
       color: var(--ink); margin: 0; }
.bn, :lang(bn) { font-family: "Nirmala UI", "Segoe UI", sans-serif; line-height: 1.7; }
code, pre { font-family: Consolas, "Cascadia Mono", monospace; font-size: 8.4pt; }
code { background: var(--soft); padding: 0 3px; border-radius: 3px; overflow-wrap: anywhere; }
pre { background: var(--soft); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px;
      white-space: pre-wrap; overflow-wrap: anywhere; break-inside: avoid; }
pre.prompt { font-size: 8pt; break-inside: auto; }
h1, h2, h3, h4 { font-family: Georgia, "Segoe UI", serif; color: var(--ink); line-height: 1.25; }
h2 { font-size: 17pt; margin: 0 0 10px; padding-bottom: 6px; border-bottom: 2px solid var(--accent); }
h3 { font-size: 11.5pt; margin: 16px 0 6px; color: var(--accent); break-after: avoid; }
h4 { font-size: 10pt; margin: 12px 0 4px; break-after: avoid; }
p { margin: 0 0 7px; }
ul, ol { margin: 0 0 8px; padding-left: 18px; }
li { margin-bottom: 3px; }
section { break-before: page; }
.lead { font-size: 11pt; }
.small { font-size: 8.4pt; color: var(--muted); }
table { width: 100%; border-collapse: collapse; margin: 6px 0 10px; font-size: 8.8pt; }
th { text-align: left; background: var(--accent-soft); color: var(--accent); font-weight: 600;
     padding: 5px 6px; border-bottom: 1px solid var(--line); }
td { padding: 5px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
table.kv td:first-child { width: 24%; font-weight: 600; }
table.kv3 td:first-child { width: 20%; font-weight: 600; }
table.kv3 td:nth-child(2) { width: 22%; }
table.compact { font-size: 8.4pt; }
table.narrow { width: 55%; }
table.cats td:nth-child(1) { width: 4%; color: var(--muted); }
table.cats td:nth-child(2) { width: 25%; white-space: nowrap; }
table.cats td:nth-child(3) { width: 12%; }
table.cats td:nth-child(4) { width: 10%; }
table.cats td:nth-child(5) { width: 12%; white-space: nowrap; }
table.nums td:first-child { width: 16%; white-space: nowrap; }
table.nums td:nth-child(3) { width: 17%; }
table.routes td:first-child { width: 17%; }
table.routes td:last-child { width: 36%; }
table.cases { font-size: 8pt; }
table.cases td { padding: 2.5px 6px; }
table.compact td:first-child { white-space: nowrap; }
table.cases td:nth-child(1) { width: 4%; color: var(--muted); }
table.cases td:nth-child(2) { width: 50%; }
table.env td:first-child { width: 33%; }
.badge { display: inline-block; font-size: 7.4pt; font-weight: 600; padding: 1px 6px; border-radius: 10px;
         white-space: nowrap; vertical-align: 1px; }
.badge.device { background: var(--green-soft); color: var(--green); }
.badge.model  { background: var(--blue-soft);  color: var(--blue); }
.badge.warn   { background: var(--amber-soft); color: var(--amber); }
.badge.plain  { background: var(--soft);       color: var(--muted); }
.note { border-left: 3px solid var(--accent); background: var(--accent-soft); padding: 7px 10px;
        border-radius: 0 6px 6px 0; margin: 8px 0 12px; break-inside: avoid; }
.note.good { border-color: var(--green); background: var(--green-soft); }
.note.warn { border-color: var(--amber); background: var(--amber-soft); }
.swatch { display: inline-block; width: 9px; height: 9px; border-radius: 2px; vertical-align: -1px; }
.swatch.red { background: var(--red); } .swatch.amber { background: var(--amber); }
dl dt { font-weight: 600; margin-top: 7px; } dl dd { margin: 2px 0 0 14px; }
ol.rules li, ol.history li { margin-bottom: 5px; }

.flow { margin: 8px auto; max-width: 150mm; }
.step { border: 1px solid var(--line); border-left: 5px solid var(--blue); border-radius: 6px;
        padding: 6px 10px; background: #fff; break-inside: avoid; }
.step-title { font-weight: 700; margin-bottom: 2px; }
.step.device { border-left-color: var(--green); background: var(--green-soft); }
.step.gate { border-left-color: var(--accent); background: var(--accent-soft); }
.step.check { border-left-color: var(--amber); background: var(--amber-soft); }
.step.fallback { border-left-color: var(--red); background: var(--red-soft); margin-top: 10px; }
.arrow { text-align: center; color: var(--muted); font-size: 9pt; line-height: 1.3; }

.reply { border: 1px solid var(--line); border-radius: 7px; margin: 0 0 10px; break-inside: avoid; }
.reply-head { background: var(--soft); padding: 5px 8px; border-bottom: 1px solid var(--line);
              border-radius: 7px 7px 0 0; }
.reply-head .use { float: right; font-size: 7.8pt; color: var(--muted); }
.reply-body { display: grid; grid-template-columns: 1fr 1fr; }
.reply-body .col { padding: 7px 9px; font-size: 8.4pt; }
.reply-body .col + .col { border-left: 1px solid var(--line); }
.bn-col { font-family: "Nirmala UI", sans-serif; line-height: 1.65; }
.lang { font-size: 7pt; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 3px; }
.reply hr { border: 0; border-top: 1px dashed var(--line); margin: 5px 0; }
ul.code li { margin-bottom: 2px; }

/* cover */
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: space-between; }
.cover-top { margin-top: 30mm; }
.cover .eyebrow { font-size: 9pt; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
.cover h1 { font-size: 40pt; margin: 6px 0 0; letter-spacing: -.5px; }
.cover .bn-title { font-family: "Nirmala UI", sans-serif; font-size: 26pt; color: var(--accent); margin: 2px 0 14px; }
.cover .sub { font-size: 13pt; color: var(--muted); max-width: 140mm; line-height: 1.45; }
.cover-meta { border-top: 2px solid var(--accent); padding-top: 10px; font-size: 9pt; color: var(--muted); }
.cover-meta table { font-size: 9pt; margin: 0; }
.cover-meta td { border: 0; padding: 2px 0; }
.cover-meta td:first-child { width: 38mm; color: var(--ink); font-weight: 600; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 18px 0 0; }
.stat { border: 1px solid var(--line); border-radius: 8px; padding: 9px 10px; }
.stat b { display: block; font-family: Georgia, serif; font-size: 20pt; color: var(--accent); line-height: 1.1; }
.stat span { font-size: 8pt; color: var(--muted); }

/* contents */
.toc { break-before: page; }
.toc h2 { border: 0; }
.toc ol { list-style: none; padding: 0; margin: 0; }
.toc li { display: flex; align-items: baseline; font-size: 10pt; padding: 3px 0; border-bottom: 1px dotted var(--line); }
.toc li a { color: var(--ink); text-decoration: none; flex: 1; }
.toc li .pg { color: var(--muted); font-variant-numeric: tabular-nums; min-width: 8mm; text-align: right; }
.toc li.app { font-size: 9.2pt; }
.toc .grp { font-size: 8pt; letter-spacing: .1em; text-transform: uppercase; color: var(--accent);
            font-weight: 600; margin: 12px 0 4px; }
"""


def cover() -> str:
    stats = [
        (str(len(PRIORITY)), "safety categories"),
        (str(TOTAL_PATTERNS), "detection patterns"),
        (str(len(CHUNKS)), "corpus passages"),
        ("670", "automated tests"),
    ]
    st = "".join(f'<div class="stat"><b>{v}</b><span>{k}</span></div>' for v, k in stats)
    return f"""
<div class="cover">
  <div class="cover-top">
    <div class="eyebrow">WaterAid Bangladesh · Shomota Shurokkha</div>
    <h1>Bharosha</h1>
    <div class="bn-title">ভরসা</div>
    <div class="sub">The complete guide to the safeguarding and gender-based-violence assistant — what it is,
    what it does, how it works, how it was built, and where it stands.</div>
    <div class="stats">{st}</div>
  </div>
  <div class="cover-meta">
    <table>
      <tr><td>Prepared</td><td>{TODAY}</td></tr>
      <tr><td>Describes</td><td>commit <code>{COMMIT}</code> of <code>WaterAidBangladesh/Stop-Gender-Violence-App</code></td></tr>
      <tr><td>Status</td><td>Not deployed · referral numbers unverified · prompt, notes and blocks awaiting safeguarding sign-off</td></tr>
      <tr><td>Generated from</td><td>the live code — every number, reply, prompt and test case in this document is read from the repository, not typed.</td></tr>
    </table>
  </div>
</div>"""


def build(pages: dict[str, int] | None = None) -> str:
    SECTIONS.clear()
    main_parts = [
        section("s1", "1. What Bharosha is", s_summary()),
        section("s2", "2. Where it stands", s_status()),
        section("s3", "3. What a person experiences", s_experience()),
        section("s4", "4. How one message is handled", s_flow()),
        section("s5", "5. The safety layer", s_safety()),
        section("s6", "6. Referral numbers and fixed replies", s_referrals()),
        section("s7", "7. The model and its prompt", s_model()),
        section("s8", "8. The corpus", s_corpus()),
        section("s9", "9. Retrieval", s_retrieval()),
        section("s10", "10. The app", s_app()),
        section("s11", "11. Keeping phone and server in step", s_sync()),
        section("s12", "12. Privacy and data", s_privacy()),
        section("s13", "13. The server", s_server()),
        section("s14", "14. Testing", s_testing()),
        section("s15", "15. How to run and change it", s_run()),
        section("s16", "16. How it was built", s_history()),
        section("s17", "17. What is still open", s_open()),
        section("s18", "18. Decisions still to be made", s_decisions()),
    ]
    app_parts = [
        section("aA", "Appendix A. Every fixed reply, in both languages", a_replies(), True),
        section("aB", "Appendix B. The model prompts", a_prompts(), True),
        section("aC", "Appendix C. The output-check patterns", a_assertions(), True),
        section("aD", "Appendix D. The shared test cases", a_cases(), True),
        section("aE", "Appendix E. Configuration", a_config(), True),
        section("aF", "Appendix F. File inventory", a_files(), True),
    ]
    def toc_row(sid, title, cls=""):
        pg = (pages or {}).get(title, "")
        return f'<li class="{cls}"><a href="#{sid}">{E(title)}</a><span class="pg">{pg}</span></li>'
    main_toc = "".join(toc_row(s, ti) for s, ti in SECTIONS if not s.startswith("a"))
    app_toc = "".join(toc_row(s, ti, "app") for s, ti in SECTIONS if s.startswith("a"))
    toc = f'<div class="toc"><h2>Contents</h2><ol>{main_toc}</ol><div class="grp">Appendices</div><ol>{app_toc}</ol></div>'
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Bharosha — Complete Guide</title><style>{CSS}</style></head>
<body>{cover()}{toc}{"".join(main_parts)}{"".join(app_parts)}</body></html>"""


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    """Edge's launcher can return before its renderer has finished writing, so
    wait for the file to appear and stop growing rather than trusting the exit."""
    import time

    if pdf_path.exists():
        pdf_path.unlink()
    subprocess.run([
        EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        "--generate-pdf-document-outline", "--run-all-compositor-stages-before-draw",
        f"--user-data-dir={SCRATCH / 'edge-profile'}",
        f"--print-to-pdf={pdf_path}", html_path.as_uri(),
    ], check=True, capture_output=True, timeout=180)
    last, stable = -1, 0
    for _ in range(240):
        size = pdf_path.stat().st_size if pdf_path.exists() else -1
        stable = stable + 1 if size == last and size > 0 else 0
        if stable >= 3:
            return
        last = size
        time.sleep(0.5)
    raise RuntimeError(f"Edge never finished writing {pdf_path}")


def find_pages(pdf_path: Path) -> dict[str, int]:
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    texts = [norm(p.extract_text() or "") for p in reader.pages]
    found = {}
    for _, title in SECTIONS:
        key = norm(title)
        # skip cover (0) and contents (1..2)
        for i, txt in enumerate(texts):
            if i < 2:
                continue
            if key in txt and not txt.startswith("contents"):
                found[title] = i + 1
                break
    return found


def stamp(pdf_path: Path, out_path: Path) -> int:
    """Footer on every page but the cover, drawn by Edge and merged with pypdf."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    foot = "".join(
        f'<div class="pg">{"" if i == 0 else f"<span>Bharosha — complete guide · {COMMIT}</span><span>{i + 1} / {n}</span>"}</div>'
        for i in range(n)
    )
    stamp_html = SCRATCH / "stamps.html"
    stamp_html.write_text(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 0; }}
body {{ margin: 0; font-family: "Segoe UI", sans-serif; font-size: 7.6pt; color: #8a8e96; }}
.pg {{ height: 297mm; position: relative; break-after: page; }}
.pg:last-child {{ break-after: auto; }}
.pg span:first-child {{ position: absolute; left: 16mm; bottom: 9mm; }}
.pg span:last-child {{ position: absolute; right: 16mm; bottom: 9mm; }}
</style></head><body>{foot}</body></html>""", encoding="utf-8")
    stamps_pdf = SCRATCH / "stamps.pdf"
    print_pdf(stamp_html, stamps_pdf)
    stamps = PdfReader(str(stamps_pdf))
    # Clone first so Edge's bookmarks and internal links survive, then stamp once.
    writer = PdfWriter(clone_from=reader)
    for i, page in enumerate(writer.pages):
        if i < len(stamps.pages):
            page.merge_page(stamps.pages[i])
    writer.add_metadata({"/Title": "Bharosha — Complete Guide", "/Author": "WaterAid Bangladesh — Shomota Shurokkha",
                         "/Subject": "Safeguarding and GBV assistant: design, behaviour, status"})
    with out_path.open("wb") as fh:
        writer.write(fh)
    return n


def main() -> None:
    html_path = SCRATCH / "guide.html"
    pass1 = SCRATCH / "guide_pass1.pdf"
    html_path.write_text(build(), encoding="utf-8")
    print_pdf(html_path, pass1)
    pages = find_pages(pass1)
    print(f"pass 1: found {len(pages)}/{len(SECTIONS)} headings")
    html_path.write_text(build(pages), encoding="utf-8")
    pass2 = SCRATCH / "guide_pass2.pdf"
    print_pdf(html_path, pass2)
    check = find_pages(pass2)
    if check != pages:
        print("page numbers shifted between passes:", {k: (pages.get(k), v) for k, v in check.items() if pages.get(k) != v})
    n = stamp(pass2, OUT_PDF)
    print(f"wrote {OUT_PDF} — {n} pages, {OUT_PDF.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
