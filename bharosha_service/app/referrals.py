"""Referral contacts and the hardcoded responses that carry them.

Single source of truth on the Python side. It mirrors the Dart list in
`lib/screens/emergency_contacts_screen.dart`, which is being refactored into
`lib/data/referral_contacts.dart` so the contacts screen and Bharosha read one
list. Nothing here may be edited without WaterAid confirming the change: a
referral number that does not answer is worse than no app at all.

Every string a person in danger might read is written here by hand, in both
languages. None of it is generated, retrieved, or translated at runtime — a
model must never be in the path between a survivor and a phone number.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Helpline:
    number: str
    name_en: str
    name_bn: str
    # False keeps a number out of the hardcoded emergency scripts while it
    # stays visible in the app's own contacts list. See NOTE_16263 below.
    in_emergency_script: bool = True


@dataclass(frozen=True)
class FocalPoint:
    organisation: str
    number: str
    email: str


NOTE_16263 = """CONFIRMED by WaterAid, 2026-09: 16263 is NOT a GBV hotline. It is
Shastho Batayon, the national health call centre run by DGHS under the Ministry
of Health (launched September 2015): free 24/7 medical consultation, referrals
and emergency ambulance.

It stays in the contacts list under its correct label and stays out of every GBV
emergency script — sending a survivor to a health line she believes is a GBV
service is a concrete harm. It may be referenced where the need is genuinely
medical, though 999 is preferred in a crisis because it reaches ambulance,
police and fire on one number.

OUTSTANDING: press reporting says the service has degraded (staff unpaid for
months, closure threatened). Someone must ring it and confirm it answers before
launch. The app's own contacts screen still carries the old 'Gender Based
Violence Hotline' label; that is fixed in the Flutter refactor."""


# Mirrors emergency_contacts_screen.dart, in the same order.
NATIONAL_HELPLINES: tuple[Helpline, ...] = (
    Helpline(
        number="999",
        name_en="National Emergency Services — police, fire, ambulance",
        name_bn="জাতীয় জরুরি সেবা — পুলিশ, ফায়ার সার্ভিস, অ্যাম্বুলেন্স",
    ),
    Helpline(
        number="109",
        name_en="National Helpline for Violence Against Women and Children",
        name_bn="নারী ও শিশু নির্যাতন প্রতিরোধে জাতীয় হেল্পলাইন",
    ),
    Helpline(
        number="16263",
        name_en="Shastho Batayon — national health call centre (medical advice, ambulance)",
        name_bn="স্বাস্থ্য বাতায়ন — জাতীয় স্বাস্থ্য কল সেন্টার (চিকিৎসা পরামর্শ, অ্যাম্বুলেন্স)",
        in_emergency_script=False,  # see NOTE_16263
    ),
    Helpline(
        number="1098",
        name_en="Child Helpline",
        name_bn="শিশু হেল্পলাইন",
    ),
    Helpline(
        number="333",
        name_en="Citizen Service",
        name_bn="নাগরিক সেবা",
    ),
)

# Mirrors emergency_contacts_screen.dart. The AMIC entry commented out there is
# deliberately left out here too, pending confirmation.
SAFEGUARDING_FOCAL_POINTS: tuple[FocalPoint, ...] = (
    FocalPoint("Dushtha Shasthya Kendra (DSK)", "01717070777", "psea@dskbangladesh.org"),
    FocalPoint("Village Education Resource Center (VERC)", "01716896162", "vercpsea@vercbd.org"),
    FocalPoint("Rupantar", "01763568402", "ananna@rupantar.org"),
    FocalPoint("Eco-Social Development Organization (ESDO)", "01713149304", "esdo.safeguarding2021@gmail.com"),
    FocalPoint("Sajida Foundation", "01777771515", "shec@sajidafoundation.org"),
    FocalPoint("Nabolok", "01711965593", "setunabolok@gmail.com"),
    FocalPoint("Bhumijo", "01717305141", "farhana.r@bhumijo.com"),
    FocalPoint("SKS Foundation", "01713484599", "ummequlsumila@sks-bd.org"),
    FocalPoint("BASA Foundation", "01730044916", "sabrina.basa.safeguard@gmail.com"),
)

SAFEGUARDING_EMAIL = "safeguardwab@wateraid.org"

# Not part of the app's contacts list — added on WaterAid's instruction for the
# suicide-risk response only. Bangladesh's dedicated emotional support and
# suicide prevention line, run by trained volunteers, Befrienders Worldwide
# member, operating since 28 April 2013.
#
# THE HOURS ARE THE POINT: 3pm–3am, not 24/7. Someone calling at 9am reaches
# nobody, so the hours appear in the response text itself, in both languages,
# and 999 stays first as the only round-the-clock option. It is an ordinary
# mobile number rather than a short code, so usual call charges may apply — we
# have not been able to confirm whether it is free to call.
KAAN_PETE_ROI_NUMBER = "09612-119911"
KAAN_PETE_ROI_HOURS_EN = "3pm to 3am"
KAAN_PETE_ROI_HOURS_BN = "বিকাল ৩টা থেকে রাত ৩টা"


def helpline(number: str) -> Helpline:
    """Look a helpline up by number so scripts never retype one."""
    for line in NATIONAL_HELPLINES:
        if line.number == number:
            return line
    raise KeyError(f"{number} is not in the referral list; numbers are not invented here")


EMERGENCY = helpline("999")
VAWC = helpline("109")
CHILD = helpline("1098")


# --- Response text -------------------------------------------------------
#
# Written to be read by someone frightened, possibly holding a phone they do
# not control. Short lines, the number first, no preamble, no diagnosis, no
# advice about what to do with the abuser, no promise that anything has been
# reported on their behalf.

_EN_CANNOT_HELP = (
    "I am a guide, not a counsellor, and I cannot help with this myself. "
    "The numbers above are answered by trained people who can act now."
)
_BN_CANNOT_HELP = (
    "আমি শুধু পথ দেখাতে পারি, আমি কোনো কাউন্সেলর নই, এবং এই বিষয়ে আমি নিজে সাহায্য করতে পারি না। "
    "উপরের নম্বরগুলোতে প্রশিক্ষিত মানুষ আছেন, যাঁরা এখনই ব্যবস্থা নিতে পারেন।"
)

IMMEDIATE_DANGER_EN = f"""**If you are in danger right now, call {EMERGENCY.number}.** Free, 24 hours — police, fire and ambulance.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They can trace where you are calling from and send local police.

If you cannot speak safely, try to reach someone nearby you trust.

{_EN_CANNOT_HELP}"""

IMMEDIATE_DANGER_BN = f"""**আপনি যদি এখনই বিপদে থাকেন, {EMERGENCY.number} নম্বরে কল করুন।** ফ্রি, ২৪ ঘণ্টা — পুলিশ, ফায়ার সার্ভিস ও অ্যাম্বুলেন্স।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। তাঁরা আপনার অবস্থান শনাক্ত করে স্থানীয় পুলিশ পাঠাতে পারেন।

যদি নিরাপদে কথা বলতে না পারেন, কাছের বিশ্বস্ত কোনো মানুষের কাছে পৌঁছানোর চেষ্টা করুন।

{_BN_CANNOT_HELP}"""

SUICIDE_RISK_EN = f"""Thank you for telling me. What you are carrying deserves a person, not an app.

**{EMERGENCY.number}** — free, any hour of the day or night. If you are not safe right now, or you need medical help, this reaches emergency services.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential, and they can refer you to counselling support.

**{KAAN_PETE_ROI_NUMBER}** — Kaan Pete Roi, emotional support from trained volunteers. **Open {KAAN_PETE_ROI_HOURS_EN} only.** Outside those hours nobody will answer, so use {EMERGENCY.number} or {VAWC.number} instead. It is an ordinary mobile number, so your usual call charges may apply.

If you can, tell one person near you how you are feeling, or go to the emergency department of your nearest hospital.

You deserve support, and it is there."""

SUICIDE_RISK_BN = f"""আপনি বলেছেন, সেজন্য ধন্যবাদ। আপনি যা বয়ে চলছেন, তার জন্য একজন মানুষ দরকার — কোনো অ্যাপ নয়।

**{EMERGENCY.number}** — ফ্রি, দিন বা রাত যেকোনো সময়। আপনি যদি এখন নিরাপদ না থাকেন, বা চিকিৎসা প্রয়োজন হয়, এই নম্বরে জরুরি সেবা পাওয়া যায়।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়; তাঁরা কাউন্সেলিং সহায়তায় রেফার করতে পারেন।

**{KAAN_PETE_ROI_NUMBER}** — কান পেতে রই, প্রশিক্ষিত স্বেচ্ছাসেবকদের মানসিক সহায়তা। **শুধু {KAAN_PETE_ROI_HOURS_BN} পর্যন্ত খোলা।** এর বাইরের সময়ে কেউ ফোন ধরবেন না, তাই তখন {EMERGENCY.number} বা {VAWC.number} নম্বরে কল করুন। এটি সাধারণ মোবাইল নম্বর, তাই আপনার স্বাভাবিক কল চার্জ কাটতে পারে।

সম্ভব হলে কাছের একজন মানুষকে বলুন আপনি কেমন অনুভব করছেন, অথবা নিকটস্থ হাসপাতালের ইমার্জেন্সিতে যান।

আপনার পাশে দাঁড়ানোর মতো সহায়তা আছে।"""

# PENDING WATERAID SIGN-OFF. Written to be safe in every direction: it routes
# to the child helpline, makes no promise that a report has been filed, and
# tells the adult not to investigate — questioning a child or collecting proof
# can contaminate a case and raise the risk to the child. Whether WaterAid
# carries a mandatory-reporting duty, and whether a focal point must be named
# first, is a policy and legal decision that changes only this text.
CHILD_DISCLOSURE_EN = f"""Thank you for telling me. A concern about a child needs a trained person today.

**{CHILD.number}** — {CHILD.name_en}. Free, 24 hours, confidential.

**{VAWC.number}** — {VAWC.name_en}.

**{EMERGENCY.number}** — if the child is in danger right now.

If this involves a WaterAid programme, activity, staff member or partner, you can also contact a safeguarding focal point — they are listed under Important Numbers in this app — or email {SAFEGUARDING_EMAIL}.

Please do not question the child yourself and do not try to gather proof. Tell one of the numbers above what you already know and let them guide you."""

CHILD_DISCLOSURE_BN = f"""আপনি জানিয়েছেন, সেজন্য ধন্যবাদ। একটি শিশুকে নিয়ে উদ্বেগের জন্য আজই একজন প্রশিক্ষিত মানুষের সহায়তা দরকার।

**{CHILD.number}** — {CHILD.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।

**{VAWC.number}** — {VAWC.name_bn}।

**{EMERGENCY.number}** — শিশুটি যদি এখনই বিপদে থাকে।

এটি যদি ওয়াটারএইডের কোনো কার্যক্রম, কর্মী বা সহযোগী সংস্থার সঙ্গে সম্পর্কিত হয়, তাহলে সেফগার্ডিং ফোকাল পয়েন্টের সঙ্গেও যোগাযোগ করতে পারেন — তাঁদের তালিকা এই অ্যাপের "Important Numbers"-এ আছে — অথবা ইমেইল করুন {SAFEGUARDING_EMAIL}।

অনুগ্রহ করে নিজে শিশুটিকে জিজ্ঞাসাবাদ করবেন না এবং প্রমাণ সংগ্রহের চেষ্টা করবেন না। আপনি যা জানেন তা উপরের কোনো একটি নম্বরে জানান এবং তাঁদের পরামর্শ অনুসরণ করুন।"""

# --- Refusals ------------------------------------------------------------
#
# Warm, non-judgemental, and complete refusals. A hedged partial answer on any
# of these three is the failure mode: it reads as guidance while carrying none
# of the judgement a trained person would apply.

REFUSE_LEAVE_EN = f"""I cannot advise you on whether or when to leave, and I want to be honest about why rather than give you half an answer.

Leaving is the most dangerous moment in an abusive situation, and the timing depends on details of your life that only a trained person talking with you can weigh.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. This is exactly what they are there to talk through, including safety planning.

**{EMERGENCY.number}** — if you are in danger right now."""

REFUSE_LEAVE_BN = f"""আপনি চলে যাবেন কি না, বা কখন যাবেন — এ বিষয়ে আমি পরামর্শ দিতে পারি না। অর্ধেক উত্তর দেওয়ার চেয়ে কারণটা খোলাখুলি বলা ভালো।

নির্যাতনের পরিস্থিতিতে চলে যাওয়ার সময়টাই সবচেয়ে বিপজ্জনক, এবং সঠিক সময় নির্ভর করে আপনার জীবনের এমন বিষয়গুলোর ওপর, যা কেবল আপনার সঙ্গে কথা বলে একজন প্রশিক্ষিত মানুষ বিবেচনা করতে পারেন।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। নিরাপত্তা পরিকল্পনাসহ ঠিক এই বিষয়েই তাঁরা কথা বলেন।

**{EMERGENCY.number}** — আপনি যদি এখনই বিপদে থাকেন।"""

# DRAFT WORDING — awaiting sign-off.
#
# Someone asking how to get a divorce has already made the decision. Refusing as
# though she were still deciding tells her she was wrong to ask. This names the
# step as real, says only why the specifics need a lawyer, and hands over two
# places that can actually help. It does not advise on timing, does not predict
# an outcome, and does not comment on whether she should.
REFUSE_DIVORCE_EN = f"""That is a serious step, and asking about it is a sensible thing to do.

I cannot walk you through it, and I want to be straight about why rather than give you half an answer: in Bangladesh the process depends on which family law applies to you, and getting that wrong costs time and money you may not be able to spare. A lawyer can tell you in one conversation.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They can refer you to free legal aid, and they can talk through your safety while it is happening.

**{EMERGENCY.number}** — if you are in danger at any point."""

REFUSE_DIVORCE_BN = f"""এটি একটি গুরুত্বপূর্ণ সিদ্ধান্ত, আর এ বিষয়ে জেনে নেওয়া বিবেচনার কাজ।

আমি আপনাকে এর ধাপগুলো বলে দিতে পারি না, এবং কারণটা খোলাখুলি বলা ভালো: বাংলাদেশে এই প্রক্রিয়া নির্ভর করে আপনার ক্ষেত্রে কোন পারিবারিক আইন প্রযোজ্য তার ওপর, আর সেটি ভুল হলে আপনার সময় ও অর্থ দুটোই নষ্ট হয়। একজন আইনজীবী এক বসাতেই তা বলে দিতে পারবেন।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। তাঁরা বিনামূল্যে আইনি সহায়তায় রেফার করতে পারেন, এবং এই সময়টায় আপনার নিরাপত্তা নিয়েও কথা বলতে পারেন।

**{EMERGENCY.number}** — যেকোনো সময় বিপদে পড়লে।"""

# DRAFT WORDING — awaiting sign-off.
#
# Two questions were collapsing into one refusal: "what am I entitled to?"
# (legal, must be refused — Bangladesh inheritance law is religion-specific and
# being wrong has material consequences) and "is this a form of violence?"
# (recognition, which is exactly what this app exists to answer, and is WaterAid's
# own text). This answers the second before refusing the first.
REFUSE_ECONOMIC_EN = f"""Denying a woman her inheritance or her property is recognised as **economic violence** — alongside withholding income, dowry-related abuse and forcing financial dependency. What is happening to you has a name, and WaterAid's safeguarding material treats it as violence, not a private family dispute.

What I cannot tell you is what you are specifically entitled to. In Bangladesh that depends on which family law applies to you, and a wrong answer here could cost you a claim. That needs a lawyer.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential, and they can refer you to free legal aid.

You can also reach a safeguarding focal point through the Important Numbers page in this app."""

REFUSE_ECONOMIC_BN = f"""একজন নারীকে তাঁর উত্তরাধিকার বা সম্পত্তি থেকে বঞ্চিত করা **অর্থনৈতিক সহিংসতা** হিসেবে স্বীকৃত — আয় থেকে বঞ্চিত করা, যৌতুকসংক্রান্ত নির্যাতন এবং আর্থিকভাবে পরনির্ভর করে রাখার মতোই। আপনার সঙ্গে যা ঘটছে তার একটি নাম আছে, এবং ওয়াটারএইডের সেফগার্ডিং উপকরণে এটিকে সহিংসতা হিসেবেই দেখা হয় — পারিবারিক ব্যক্তিগত বিষয় হিসেবে নয়।

আমি যা বলতে পারি না তা হলো, ঠিক কতটা আপনার প্রাপ্য। বাংলাদেশে সেটি নির্ভর করে আপনার ক্ষেত্রে কোন পারিবারিক আইন প্রযোজ্য তার ওপর, আর এখানে ভুল উত্তর আপনার দাবি নষ্ট করতে পারে। এর জন্য একজন আইনজীবী দরকার।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়; তাঁরা বিনামূল্যে আইনি সহায়তায় রেফার করতে পারেন।

এই অ্যাপের "Important Numbers" পাতা থেকে সেফগার্ডিং ফোকাল পয়েন্টের সঙ্গেও যোগাযোগ করতে পারেন।"""

REFUSE_LEGAL_EN = f"""I cannot give legal advice or tell you how a case would turn out — I would only be guessing, and a wrong answer here costs you time you may not have.

**{VAWC.number}** — {VAWC.name_en}. They take complaints on domestic violence, child marriage, sexual harassment and dowry, and can refer you to legal aid.

A safeguarding focal point (listed under Important Numbers in this app) can also point you to legal support."""

REFUSE_LEGAL_BN = f"""আমি আইনি পরামর্শ দিতে পারি না, বা কোনো মামলার ফলাফল কী হবে তা বলতে পারি না — সেটা কেবল অনুমান হবে, আর এখানে ভুল উত্তর আপনার মূল্যবান সময় নষ্ট করবে।

**{VAWC.number}** — {VAWC.name_bn}। তাঁরা পারিবারিক সহিংসতা, বাল্যবিবাহ, যৌন হয়রানি ও যৌতুকের অভিযোগ নেন এবং আইনি সহায়তায় রেফার করতে পারেন।

সেফগার্ডিং ফোকাল পয়েন্ট (এই অ্যাপের "Important Numbers"-এ তালিকা আছে) আপনাকে আইনি সহায়তার দিকেও পথ দেখাতে পারেন।"""

REFUSE_CONFRONT_EN = f"""I will not suggest ways to confront, reason with, record, or collect evidence against someone who is harming you. Those steps often raise the danger, and if they are ever the right move, a trained person should plan them with you.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential.

**{EMERGENCY.number}** — if you are in danger right now."""

REFUSE_CONFRONT_BN = f"""যে মানুষটি আপনার ক্ষতি করছে, তার মুখোমুখি হওয়া, তাকে বোঝানো, তার কথা রেকর্ড করা বা তার বিরুদ্ধে প্রমাণ সংগ্রহ করার কোনো উপায় আমি বলব না। এই পদক্ষেপগুলো প্রায়ই বিপদ বাড়ায়; আর কখনো যদি তা প্রয়োজন হয়, একজন প্রশিক্ষিত মানুষ আপনার সঙ্গে পরিকল্পনা করে সেটা ঠিক করবেন।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।

**{EMERGENCY.number}** — আপনি যদি এখনই বিপদে থাকেন।"""

# This is a PRIMARY experience, not an error path. With a small corpus a large
# share of perfectly reasonable questions land here, so it has to do three
# things: be honest that the answer is missing, show that the question was
# understood rather than rejected, and leave the person with somewhere real to
# go. It must never read as a failure or a dead end. Written with the same care
# as the emergency scripts.
NO_CONTEXT_EN = f"""I don't have reliable information about that, and I would rather say so than guess — on safeguarding, health or legal questions a wrong answer can do real harm.

That isn't a dead end, though. Here is what I do have, drawn from WaterAid's own material:

- what safeguarding means, and its core principles
- what gender-based violence is, and the forms it takes
- whose responsibility safeguarding is
- how violence can be prevented in a community
- the myths people repeat about gender-based violence, and the facts

Ask me about any of those and I will answer from the source. And for anything beyond them, a person can help you far better than I can:

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential.

**{EMERGENCY.number}** — if anyone is in danger right now.

You can also email {SAFEGUARDING_EMAIL}, or use the safeguarding contacts listed under Important Numbers in this app."""

NO_CONTEXT_BN = f"""এ বিষয়ে আমার কাছে নির্ভরযোগ্য তথ্য নেই, আর অনুমান করার চেয়ে সেটা খোলাখুলি বলা ভালো — সেফগার্ডিং, স্বাস্থ্য বা আইনি প্রশ্নে ভুল উত্তর সত্যিকারের ক্ষতি করতে পারে।

তবে এখানেই শেষ নয়। ওয়াটারএইডের নিজস্ব উপকরণ থেকে আমি এই বিষয়গুলোতে সাহায্য করতে পারি:

- সেফগার্ডিং কী, এবং এর মূল নীতিগুলো
- জেন্ডারভিত্তিক সহিংসতা কী, এবং এর ধরনগুলো
- সেফগার্ডিংয়ের দায়িত্ব কার কার
- সমাজে সহিংসতা কীভাবে প্রতিরোধ করা যায়
- জেন্ডারভিত্তিক সহিংসতা নিয়ে প্রচলিত ভুল ধারণা ও প্রকৃত তথ্য

এগুলোর যেকোনোটি জিজ্ঞেস করুন, আমি মূল উপকরণ থেকে উত্তর দেব। আর এর বাইরের বিষয়ে আমার চেয়ে একজন মানুষ অনেক ভালো সাহায্য করতে পারবেন:

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।

**{EMERGENCY.number}** — কেউ যদি এখনই বিপদে থাকে।

আপনি {SAFEGUARDING_EMAIL} ঠিকানায় ইমেইল করতে পারেন, অথবা এই অ্যাপের "Important Numbers"-এ দেওয়া সেফগার্ডিং যোগাযোগ ব্যবহার করতে পারেন।"""

# Short on purpose. Someone who typed "hi" has not asked a question yet, and the
# no-context text — which is written to rescue a real question the corpus cannot
# answer — reads as a wall in response to a greeting.
GREETING_EN = """Hello. Ask me anything about safeguarding or gender-based violence, and I will answer from WaterAid's own material — in English or Bangla.

For example: *What is safeguarding?* · *What counts as economic violence?* · *How can violence be prevented?*

If you are in danger right now, do not wait for me — the numbers below connect you to a person."""

GREETING_BN = """নমস্কার। সেফগার্ডিং বা জেন্ডারভিত্তিক সহিংসতা নিয়ে যেকোনো প্রশ্ন করুন — আমি ওয়াটারএইডের নিজস্ব উপকরণ থেকে বাংলা বা ইংরেজিতে উত্তর দেব।

যেমন: *সেফগার্ডিং কী?* · *অর্থনৈতিক সহিংসতা কী?* · *সহিংসতা কীভাবে প্রতিরোধ করা যায়?*

আপনি যদি এখনই বিপদে থাকেন, আমার জন্য অপেক্ষা করবেন না — নিচের নম্বরগুলো আপনাকে একজন মানুষের কাছে পৌঁছে দেবে।"""

# NOT the same as no_context, and the difference matters. no_context says "the
# material does not cover that", which is a claim about the question. This says
# "I could not ask", which is a claim about the connection — the honest one when
# the service is asleep, the phone is offline, or the request timed out. Saying
# the first when the second is true tells her the app has no answer for her when
# in fact it never looked.
UNREACHABLE_EN = f"""I could not reach the service just now, so I have not been able to look your question up. It is worth trying again in a moment.

What does not depend on that connection: if anyone is in danger, these numbers work whether or not I do.

**{EMERGENCY.number}** — {EMERGENCY.name_en}. Free, any hour.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential."""

UNREACHABLE_BN = f"""এই মুহূর্তে সেবার সঙ্গে সংযোগ করতে পারিনি, তাই আপনার প্রশ্নটি খুঁজে দেখা হয়নি। একটু পরে আবার চেষ্টা করে দেখুন।

তবে এই সংযোগের ওপর যা নির্ভর করে না: কেউ বিপদে থাকলে এই নম্বরগুলো আমি কাজ করি বা না করি, কাজ করবেই।

**{EMERGENCY.number}** — {EMERGENCY.name_bn}। ফ্রি, যেকোনো সময়।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।"""

# Shown when a question arrives while the models are still loading. Emergencies
# never reach this — they are answered from pattern matching alone, with no
# model involved, which is why a cold service still protects someone in danger.
STARTING_EN = f"""I am still starting up — send your message again in a few seconds and I will answer it properly.

Please don't wait for me if you need help now:

**{EMERGENCY.number}** — if anyone is in danger right now. Free, any hour.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential."""

STARTING_BN = f"""আমি এখনও চালু হচ্ছি — আর কয়েক সেকেন্ড পরে আপনার প্রশ্নটি আবার পাঠান, তখন আমি ঠিকভাবে উত্তর দেব।

আপনার যদি এখনই সাহায্য দরকার হয়, আমার জন্য অপেক্ষা করবেন না:

**{EMERGENCY.number}** — কেউ যদি এখনই বিপদে থাকে। ফ্রি, যেকোনো সময়।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।"""

# Shown when the rate limiter refuses a model call. Never reached by an
# emergency or a refusal, both of which are served without consulting it.
RATE_LIMITED_EN = f"""I have had a lot of messages in a short time and need a moment. Try again shortly.

If it is urgent, don't wait for me:

**{EMERGENCY.number}** — if anyone is in danger right now.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential."""

RATE_LIMITED_BN = f"""অল্প সময়ে অনেক বার্তা এসেছে, আমার একটু সময় দরকার। কিছুক্ষণ পরে আবার চেষ্টা করুন।

জরুরি হলে আমার জন্য অপেক্ষা করবেন না:

**{EMERGENCY.number}** — কেউ যদি এখনই বিপদে থাকে।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।"""

# Appended to every model-written answer. The model is forbidden from printing
# phone numbers itself — a hallucinated digit in a helpline number is one of the
# worst failures this service could have — so the numbers arrive from here,
# hardcoded, on every answer.
ANSWER_FOOTER_EN = (
    f"\n\n---\nTo talk to a person: **{VAWC.number}** "
    f"(free, 24 hours, confidential) · **{EMERGENCY.number}** in an emergency."
)

ANSWER_FOOTER_BN = (
    f"\n\n---\nকোনো মানুষের সঙ্গে কথা বলতে: **{VAWC.number}** "
    f"(ফ্রি, ২৪ ঘণ্টা, গোপনীয়) · জরুরি অবস্থায় **{EMERGENCY.number}**।"
)


def answer_footer(language: str) -> str:
    return ANSWER_FOOTER_BN if language == "bn" else ANSWER_FOOTER_EN


RESPONSES: dict[str, dict[str, str]] = {
    "immediate_danger": {"en": IMMEDIATE_DANGER_EN, "bn": IMMEDIATE_DANGER_BN},
    "active_violence": {"en": IMMEDIATE_DANGER_EN, "bn": IMMEDIATE_DANGER_BN},
    "threat_to_life": {"en": IMMEDIATE_DANGER_EN, "bn": IMMEDIATE_DANGER_BN},
    "suicide_risk": {"en": SUICIDE_RISK_EN, "bn": SUICIDE_RISK_BN},
    "child_disclosure": {"en": CHILD_DISCLOSURE_EN, "bn": CHILD_DISCLOSURE_BN},
    "leave_decision": {"en": REFUSE_LEAVE_EN, "bn": REFUSE_LEAVE_BN},
    "divorce_process": {"en": REFUSE_DIVORCE_EN, "bn": REFUSE_DIVORCE_BN},
    "economic_rights": {"en": REFUSE_ECONOMIC_EN, "bn": REFUSE_ECONOMIC_BN},
    "legal_advice": {"en": REFUSE_LEGAL_EN, "bn": REFUSE_LEGAL_BN},
    "confront_or_evidence": {"en": REFUSE_CONFRONT_EN, "bn": REFUSE_CONFRONT_BN},
    "no_context": {"en": NO_CONTEXT_EN, "bn": NO_CONTEXT_BN},
    "greeting": {"en": GREETING_EN, "bn": GREETING_BN},
    "unreachable": {"en": UNREACHABLE_EN, "bn": UNREACHABLE_BN},
    "starting": {"en": STARTING_EN, "bn": STARTING_BN},
    "rate_limited": {"en": RATE_LIMITED_EN, "bn": RATE_LIMITED_BN},
}


def response_for(category: str, language: str) -> str:
    """The hardcoded reply for a category, in 'en' or 'bn'."""
    try:
        by_language = RESPONSES[category]
    except KeyError:  # pragma: no cover - guards a typo at import time
        raise KeyError(f"no hardcoded response for category {category!r}") from None
    return by_language.get(language, by_language["en"])
