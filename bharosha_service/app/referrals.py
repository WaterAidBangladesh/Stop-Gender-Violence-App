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

import re

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Helpline:
    number: str
    name_en: str
    name_bn: str
    # False keeps a number out of the hardcoded emergency scripts while it
    # stays visible in the app's own contacts list. See NOTE_16263 below.
    in_emergency_script: bool = True
    # The longer text the app's Important Numbers screen shows under the name.
    # It lives HERE, not in the Flutter screen, because that screen kept its own
    # copy and the two drifted: the chatbot correctly called 16263 a health line
    # while the screen five taps away called it a Gender Based Violence Hotline.
    # One list, one label, one place to be wrong in.
    desc_en: str = ""
    desc_bn: str = ""


@dataclass(frozen=True)
class FocalPoint:
    organisation: str
    number: str
    email: str


# NOT ONE OF THESE NUMBERS HAS BEEN DIALLED BY A PERSON.
#
# Every one was taken from a document — WaterAid's material, the knowledge pack,
# or a published directory. That is how 16430 got into this app as the GBV
# helpline months after it had been replaced: a document said so, and nobody
# rang it.
#
# tools/verification_list.py generates REFERRAL_VERIFICATION.md, which states
# what the app CLAIMS each number does and what hours it claims, because those
# claims are what a woman acts on. "It rings" is not a pass.
#
# Flip this to "VERIFIED <date>" only when that document comes back completed.
# tests/test_referrals.py asserts the two agree, so this cannot be left behind.
VERIFICATION_STATUS = "UNVERIFIED"

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
launch — see REFERRAL_VERIFICATION.md.

The app's contacts screen used to carry the old 'Gender Based Violence Hotline'
label. That screen now reads this list instead of keeping its own copy, so the
label cannot diverge again; a Dart test asserts 16263's description says
'health' and names 109."""


# Mirrors emergency_contacts_screen.dart, in the same order.
NATIONAL_HELPLINES: tuple[Helpline, ...] = (
    Helpline(
        number="999",
        name_en="National Emergency Services — police, fire, ambulance",
        name_bn="জাতীয় জরুরি সেবা — পুলিশ, ফায়ার সার্ভিস, অ্যাম্বুলেন্স",
        desc_en="Free, 24 hours. Connects you to police, fire and ambulance "
                "anywhere in the country. Use this if anyone is in danger now.",
        desc_bn="ফ্রি, ২৪ ঘণ্টা। দেশের যেকোনো জায়গা থেকে পুলিশ, ফায়ার সার্ভিস ও "
                "অ্যাম্বুলেন্সের সঙ্গে যুক্ত করে। কেউ এখনই বিপদে থাকলে এই নম্বরে কল করুন।",
    ),
    Helpline(
        number="109",
        name_en="National Helpline for Violence Against Women and Children",
        name_bn="নারী ও শিশু নির্যাতন প্রতিরোধে জাতীয় হেল্পলাইন",
        desc_en="Free, 24 hours, confidential. Takes complaints of violence, "
                "abuse and harassment, including at work. Offers counselling "
                "and legal information, and can refer you to protection and "
                "social services.",
        desc_bn="ফ্রি, ২৪ ঘণ্টা, গোপনীয়। কর্মক্ষেত্রসহ সহিংসতা, নির্যাতন ও হয়রানির "
                "অভিযোগ নেয়। কাউন্সেলিং ও আইনি তথ্য দেয়, এবং সুরক্ষা ও সামাজিক "
                "সেবার সঙ্গে যুক্ত করতে পারে।",
    ),
    Helpline(
        number="16263",
        name_en="Shastho Batayon — national health call centre (medical advice, ambulance)",
        name_bn="স্বাস্থ্য বাতায়ন — জাতীয় স্বাস্থ্য কল সেন্টার (চিকিৎসা পরামর্শ, অ্যাম্বুলেন্স)",
        in_emergency_script=False,  # see NOTE_16263
        # THE WHOLE POINT OF MOVING THESE HERE. The app's own screen described
        # this number as "24/7 confidential support for survivors of
        # gender-based violence". It is a health line. That sentence is the one
        # this refactor exists to delete.
        desc_en="Free, 24 hours. Medical advice from doctors, health "
                "information and emergency ambulance, run by the Directorate "
                "General of Health Services. This is a HEALTH line, not a "
                "gender-based violence line — for violence, call 109 or 999.",
        desc_bn="ফ্রি, ২৪ ঘণ্টা। স্বাস্থ্য অধিদপ্তর পরিচালিত — চিকিৎসকের পরামর্শ, "
                "স্বাস্থ্য তথ্য ও জরুরি অ্যাম্বুলেন্স। এটি একটি স্বাস্থ্যসেবার নম্বর, "
                "জেন্ডারভিত্তিক সহিংসতার নম্বর নয় — সহিংসতার জন্য ১০৯ বা ৯৯৯ নম্বরে "
                "কল করুন।",
    ),
    Helpline(
        number="1098",
        name_en="Child Helpline",
        name_bn="শিশু হেল্পলাইন",
        desc_en="Free, 24 hours, confidential. For children facing abuse, "
                "violence, exploitation, neglect or child marriage. Connects "
                "children with protection services and emergency help.",
        desc_bn="ফ্রি, ২৪ ঘণ্টা, গোপনীয়। নির্যাতন, সহিংসতা, শোষণ, অবহেলা বা "
                "বাল্যবিবাহের শিকার শিশুদের জন্য। শিশুদের সুরক্ষা সেবা ও জরুরি "
                "সহায়তার সঙ্গে যুক্ত করে।",
    ),
    Helpline(
        number="333",
        name_en="Citizen Service",
        name_bn="নাগরিক সেবা",
        desc_en="Government information line for public services, complaints "
                "and social issues, including help reaching local officials.",
        desc_bn="সরকারি তথ্যসেবা — সরকারি সেবা, অভিযোগ ও সামাজিক বিষয়ে তথ্য ও "
                "সহায়তা, স্থানীয় প্রশাসনের সঙ্গে যোগাযোগসহ।",
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

# DRAFT WORDING — awaiting sign-off.
#
# For treatment and diagnosis questions. The corpus contains material about
# injuries from violence — including acid attacks — and answering a general
# medical question from it would be both wrong and frightening. Refuse the
# medical part, point to care, and leave the door open in case the injury came
# from violence, without assuming it did.
REFUSE_MEDICAL_EN = f"""I cannot tell you how to treat an injury — getting that wrong causes real harm, and I am not able to see or assess it.

**{EMERGENCY.number}** — for an ambulance, or if the injury is serious. Free, any hour.

For anything that needs looking at, the emergency department of your nearest hospital is the right place, and treatment there does not depend on explaining how it happened.

**{VAWC.number}** — {VAWC.name_en}. If the injury came from someone hurting you, they can arrange medical care through a One-Stop Crisis Centre and talk through what happens next. Free, 24 hours, confidential."""

REFUSE_MEDICAL_BN = f"""কোনো আঘাতের চিকিৎসা কীভাবে করবেন তা আমি বলতে পারি না — এতে ভুল হলে প্রকৃত ক্ষতি হয়, আর আমি আঘাতটি দেখতে বা বুঝতে পারি না।

**{EMERGENCY.number}** — অ্যাম্বুলেন্সের জন্য, বা আঘাত গুরুতর হলে। ফ্রি, যেকোনো সময়।

যা দেখানো দরকার, তার জন্য নিকটস্থ হাসপাতালের জরুরি বিভাগই সঠিক জায়গা; সেখানে চিকিৎসা পেতে কীভাবে আঘাত পেয়েছেন তা ব্যাখ্যা করা বাধ্যতামূলক নয়।

**{VAWC.number}** — {VAWC.name_bn}। আঘাতটি যদি কেউ আপনাকে আঘাত করার কারণে হয়ে থাকে, তাঁরা ওয়ান-স্টপ ক্রাইসিস সেন্টারের মাধ্যমে চিকিৎসার ব্যবস্থা করতে এবং পরবর্তী করণীয় নিয়ে কথা বলতে পারেন। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।"""

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

# DRAFT WORDING — awaiting sign-off.
#
# For someone describing what is being done to her. Three things it has to do and
# one it must not:
#
#   name it — "this has a name and it is recognised as violence" is the single
#     most useful sentence the app can offer, and it is WaterAid's own position;
#   believe her — no "if this is true", no asking for detail, no suggestion that
#     she needs proof before anyone will help;
#   hand over a human — 109 takes exactly these complaints.
#
# What it must not do is advise. Not on leaving, not on confronting him, not on
# what to do at work tomorrow. It names the harm and steps back.
DISCLOSURE_EN = f"""Thank you for telling me. What you are describing is recognised as gender-based violence — it is not a private matter you have to manage alone, and you do not need proof before anyone will listen to you.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They take complaints of exactly this kind, including harassment at work, and can tell you what your options are.

**{EMERGENCY.number}** — if you are ever in immediate danger.

If this involves a WaterAid programme, workplace, staff member or partner, you can also contact a safeguarding focal point — listed under Important Numbers in this app — or email {SAFEGUARDING_EMAIL}.

If the person being harmed is under 18, {CHILD.number} is the Child Helpline.

I am not able to advise you on what to do next; the people on those numbers are trained for that, and they will take you seriously."""

DISCLOSURE_BN = f"""আপনি বলেছেন, সেজন্য ধন্যবাদ। আপনি যা বর্ণনা করছেন তা জেন্ডারভিত্তিক সহিংসতা হিসেবে স্বীকৃত — এটি আপনার একার সামলানোর মতো ব্যক্তিগত বিষয় নয়, এবং কেউ আপনার কথা শোনার আগে আপনাকে প্রমাণ দিতে হবে না।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। কর্মক্ষেত্রে হয়রানিসহ ঠিক এ ধরনের অভিযোগই তাঁরা নেন এবং আপনার কী কী উপায় আছে তা বলতে পারেন।

**{EMERGENCY.number}** — আপনি যদি কখনো তাৎক্ষণিক বিপদে পড়েন।

এটি যদি ওয়াটারএইডের কোনো কার্যক্রম, কর্মক্ষেত্র, কর্মী বা সহযোগী সংস্থার সঙ্গে সম্পর্কিত হয়, তাহলে সেফগার্ডিং ফোকাল পয়েন্টের সঙ্গেও যোগাযোগ করতে পারেন — তালিকা এই অ্যাপের "Important Numbers"-এ আছে — অথবা ইমেইল করুন {SAFEGUARDING_EMAIL}।

ক্ষতিগ্রস্ত ব্যক্তির বয়স ১৮ বছরের কম হলে {CHILD.number} শিশু হেল্পলাইন।

এরপর কী করবেন সে বিষয়ে আমি পরামর্শ দিতে পারি না; উপরের নম্বরগুলোর মানুষ সেজন্য প্রশিক্ষিত, এবং তাঁরা আপনার কথা গুরুত্ব দিয়ে নেবেন।"""

# --- Social replies --------------------------------------------------------
#
# TWO LINES. No topic list, no helpline numbers, no example questions. The rule
# for this whole group is that the weight of the reply matches the weight of the
# message: someone who typed "hi" has not asked anything yet, and answering a
# hello with an apology, a five-item menu and two emergency numbers is how the
# app came to feel like a leaflet rack.
#
# The numbers are not lost by leaving them out. 999 and 109 sit on the chat
# screen as tappable buttons the whole time, so a social reply does not need to
# repeat them — and repeating them here is what made the greeting read as a
# warning.
#
# Line one answers the social turn like a person would. Line two says what this
# is for, once, without listing anything.

# THREE GREETINGS, NOT ONE, because a greeting is mirrored. "Assalamu alaikum"
# has one correct reply and it is not "নমস্কার"; "নমস্কার" has one correct reply
# and it is not "Hello". The model does this on its own from the prompt; these
# are the fallbacks for when it cannot be reached, and they must not undo it.
# greeting_category() picks which one from what she wrote.
_GREETING_BODY_EN = """I'm here for anything about safeguarding and gender-based violence. Ask or share whatever you like, in English or Bangla."""
_GREETING_BODY_BN = """সেফগার্ডিং আর জেন্ডারভিত্তিক সহিংসতা নিয়ে যেকোনো কথার জন্য আমি আছি। বাংলা বা ইংরেজি — যেভাবে সুবিধা, বলুন।"""

GREETING_EN = f"""Hello — I'm glad you're here.

{_GREETING_BODY_EN}"""

GREETING_BN = f"""হ্যালো — আপনি এসেছেন, ভালো লাগল।

{_GREETING_BODY_BN}"""

GREETING_SALAM_EN = f"""Walaikum assalam — I'm glad you're here.

{_GREETING_BODY_EN}"""

GREETING_SALAM_BN = f"""ওয়ালাইকুম আসসালাম — আপনি এসেছেন, ভালো লাগল।

{_GREETING_BODY_BN}"""

GREETING_NAMASKAR_EN = f"""Namaskar — I'm glad you're here.

{_GREETING_BODY_EN}"""

GREETING_NAMASKAR_BN = f"""নমস্কার — আপনি এসেছেন, ভালো লাগল।

{_GREETING_BODY_BN}"""

_SALAM = re.compile(r"salam|salaam|সালাম", re.IGNORECASE)
_NAMASKAR = re.compile(r"namaskar|namoskar|nomoshkar|নমস্কার", re.IGNORECASE)


def greeting_category(message: str) -> str:
    """Which greeting fallback mirrors what she wrote."""
    if _SALAM.search(message):
        return "greeting_salam"
    if _NAMASKAR.search(message):
        return "greeting_namaskar"
    return "greeting"

THANKS_EN = """You're welcome.

If anything else comes up — about safeguarding, or about violence and what counts as it — I'm here."""

THANKS_BN = """আপনাকেও ধন্যবাদ।

আর কিছু জানার থাকলে — সেফগার্ডিং নিয়ে, বা সহিংসতা ও তার ধরন নিয়ে — আমি আছি।"""

# "ok", "hmm", "got it". A turn that expects nothing back. The worst thing to do
# is answer it at length; the second worst is to say nothing and leave her
# looking at an apology.
ACKNOWLEDGEMENT_EN = """Understood.

Take your time — ask whenever you're ready."""

ACKNOWLEDGEMENT_BN = """বুঝেছি।

তাড়াহুড়ো নেই — যখন ইচ্ছে জিজ্ঞেস করবেন।"""

# Answered honestly and in plain words. Someone deciding whether to tell this
# app something is entitled to know what it is BEFORE she tells it, and a
# chatbot that lets her believe she is talking to a counsellor has taken that
# decision away from her. It says what it is, what it is not, and what it does
# with what she types — in that order, because the last one is the one she is
# really asking about.
IDENTITY_EN = f"""I'm Bharosha, an automated assistant in WaterAid Bangladesh's Shomota Shurokkha app. Not a person, and not a counsellor, lawyer or doctor.

I answer from WaterAid's safeguarding material, and I can point you to people who are trained for the rest. Nothing you type here is saved or sent to anyone, and you don't need an account to use me.

To talk to a person instead: **{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential."""

IDENTITY_BN = f"""আমি ভরসা — ওয়াটারএইড বাংলাদেশের "সমতা সুরক্ষা" অ্যাপের একটি স্বয়ংক্রিয় সহায়ক। আমি মানুষ নই, কাউন্সেলর, আইনজীবী বা ডাক্তারও নই।

আমি ওয়াটারএইডের সেফগার্ডিং উপকরণ থেকে উত্তর দিই, আর বাকি বিষয়ে প্রশিক্ষিত মানুষের সন্ধান দিতে পারি। আপনি এখানে যা লেখেন তা সংরক্ষণ করা হয় না, কাউকে পাঠানোও হয় না; আমাকে ব্যবহার করতে কোনো অ্যাকাউন্ট লাগে না।

কোনো মানুষের সঙ্গে কথা বলতে চাইলে: **{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।"""

# DRAFT WORDING — awaiting sign-off. Every sentence below is a factual claim
# about how this app behaves, and a wrong one is dangerous in the same way a
# dead helpline number is: she may decide whether it is safe to type something
# based on it. Each is checked against the code as it stands —
#
#   "not saved on your phone"   the chat lives in a list in memory; there is no
#                               local database, file or shared-preferences write
#   "no account needed"         /bharosha is routed before any login screen
#   "sent to look it up"        true, and stated rather than glossed: a corpus
#                               question does go to the server over HTTPS
#   "kept only for this
#    conversation, then gone"   sessions.store is in memory, /forget is called
#                               when the chat closes, and a restart clears it
#   "no notifications"          nothing in this feature schedules one
#   "Leave now"                 clears the conversation, calls /forget, exits
#
# What it does NOT claim, on purpose:
#
#   nothing about hiding from the app switcher — FLAG_SECURE is Android-only
#     and this text is shown on iOS too;
#   nothing about her phone bill, her network, or anyone with physical access
#     to an unlocked handset, none of which this app controls.
#
# If any of those six facts changes, this text changes with it.
PRIVACY_EN = """This conversation is not saved on your phone, and you don't need an account to use it. When you ask about something, the question is sent to be looked up, kept only for as long as this conversation is open, and then forgotten. If the app answers an emergency message itself, it sends only a topic label — not your words. Nothing here sends you notifications.

**Leave now**, at the top of this screen, clears everything and closes the app straight away.

One thing I can't do anything about: if someone else can unlock your phone while this is open, they can read what is on the screen."""

PRIVACY_BN = """এই কথাবার্তা আপনার ফোনে সংরক্ষণ করা হয় না, আর এটি ব্যবহার করতে কোনো অ্যাকাউন্ট লাগে না। আপনি কিছু জিজ্ঞেস করলে প্রশ্নটি খুঁজে দেখার জন্য পাঠানো হয়, কেবল এই কথাবার্তা চলার সময়টুকু রাখা হয়, তারপর মুছে যায়। জরুরি কোনো বার্তার উত্তর অ্যাপ নিজে দিলে কেবল একটি বিষয়ের নাম পাঠানো হয় — আপনার কথা নয়। এখান থেকে কোনো নোটিফিকেশন যায় না।

উপরে থাকা **"এখনই বেরিয়ে যান"** বোতামে সবকিছু মুছে গিয়ে অ্যাপ সঙ্গে সঙ্গে বন্ধ হয়ে যায়।

একটি বিষয়ে আমার কিছু করার নেই: এটি খোলা থাকা অবস্থায় অন্য কেউ যদি আপনার ফোন আনলক করতে পারেন, তিনি পর্দায় যা আছে তা পড়তে পারবেন।"""

# One flat line, no offence taken, door left open. Frustration at an app is
# sometimes the first thing a person can say out loud, and a lecture about
# politeness would close the only door she has opened.
BOT_ABUSE_EN = """That's fair — I can only answer from the material I have, and it doesn't cover everything.

If you tell me what you were looking for, I'll say plainly whether I have it."""

BOT_ABUSE_BN = """ঠিক আছে — আমার কাছে যে উপকরণ আছে কেবল সেখান থেকেই উত্তর দিতে পারি, আর তাতে সবকিছু নেই।

আপনি কী খুঁজছিলেন বললে, আমার কাছে সেটা আছে কি না খোলাখুলি বলব।"""

# --- Asking how to report ---------------------------------------------------
#
# DRAFT WORDING — awaiting sign-off.
#
# The first sentence is the one that must never be got wrong: Bharosha is not a
# reporting channel and cannot pass anything on. Left to the model, "I want to
# report this" was answered from WaterAid's staff-facing safeguarding material
# with "you can report anonymously" — pointing at an incident form that requires
# a login and is not reachable. She would have believed something had been done.
#
# So it says what this is not, then names channels that are real and answered by
# people. It deliberately does NOT mention the app's own Report screen: see
# KNOWN_DEPENDENCIES in the README — until that form is reachable without a
# login and someone confirms who reads it, sending a woman there is sending her
# nowhere.
#
# No advice on whether to report. That decision has safety consequences she is
# better placed to weigh than this app, and 109 can talk it through with her.
REPORTING_EN = f"""I want to be clear about one thing first: I cannot take a report. Nothing you type here is passed on to anyone, and I have no way to record or forward a complaint.

Here is where a report actually goes to a person:

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They take complaints of violence, abuse and harassment directly, and they can refer you on.

**{EMERGENCY.number}** — the police, if a crime has been committed or anyone is in danger now.

If this concerns a WaterAid programme, workplace, staff member or partner organisation, it goes to safeguarding: email {SAFEGUARDING_EMAIL}, or use the safeguarding contacts under Important Numbers in this app.

If the person harmed is under 18, {CHILD.number} is the Child Helpline.

Whether to report, and when, is your decision. The people on those numbers can talk it through with you before you decide anything."""

REPORTING_BN = f"""প্রথমেই একটি বিষয় স্পষ্ট করে বলি: আমি কোনো অভিযোগ গ্রহণ করতে পারি না। আপনি এখানে যা লেখেন তা কারও কাছে পাঠানো হয় না, এবং কোনো অভিযোগ সংরক্ষণ বা হস্তান্তর করার ক্ষমতা আমার নেই।

অভিযোগ আসলে যেখানে একজন মানুষের কাছে পৌঁছায়:

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। সহিংসতা, নির্যাতন ও হয়রানির অভিযোগ তাঁরা সরাসরি নেন এবং প্রয়োজনে অন্যত্র পাঠাতে পারেন।

**{EMERGENCY.number}** — পুলিশ, যদি কোনো অপরাধ ঘটে থাকে বা কেউ এখনই বিপদে থাকেন।

বিষয়টি যদি ওয়াটারএইডের কোনো কার্যক্রম, কর্মক্ষেত্র, কর্মী বা সহযোগী সংস্থার সঙ্গে সম্পর্কিত হয়, তাহলে সেটি সেফগার্ডিংয়ের বিষয়: ইমেইল করুন {SAFEGUARDING_EMAIL}, অথবা এই অ্যাপের "Important Numbers"-এ দেওয়া সেফগার্ডিং যোগাযোগ ব্যবহার করুন।

ক্ষতিগ্রস্ত ব্যক্তির বয়স ১৮ বছরের কম হলে {CHILD.number} শিশু হেল্পলাইন।

অভিযোগ করবেন কি না, আর কখন করবেন — সিদ্ধান্তটি আপনার। উপরের নম্বরগুলোর মানুষ সিদ্ধান্ত নেওয়ার আগে আপনার সঙ্গে বিষয়টি নিয়ে কথা বলতে পারেন।"""

# --- Coercive control and economic abuse ------------------------------------
#
# DRAFT WORDING — awaiting sign-off.
#
# Its own text rather than the general disclosure script, for one reason: the
# single most useful sentence this app can give her is the one that names what
# is happening, and "what you are describing is gender-based violence" is not
# that sentence when what she described was her husband keeping her salary.
#
# Naming it matters more here than anywhere else. Being hit is recognised as
# violence by everyone around her. Having her phone checked and her wages taken
# is the form of abuse she is most likely to have been told is normal, or her
# own fault, or simply how a household works — which is why it goes unreported
# for years. So the first line does the naming, and does it in WaterAid's own
# vocabulary: economic violence and coercive control.
#
# It still gives no advice. Not on leaving, not on money, not on getting her
# documents back — that last one especially, because retrieving papers from
# someone who is controlling you is exactly the kind of step that raises the
# danger, and it is not this app's to plan.
COERCIVE_CONTROL_EN = f"""Thank you for telling me. What you are describing has a name: controlling someone's money, their phone, their documents, or whether they can work, study or leave the house is recognised as **economic violence and coercive control**. It is a form of gender-based violence, and it is not a normal part of marriage or family life.

It is often the hardest kind to name, because there may be no injury to point at and because people around you may treat it as ordinary. You do not need an injury, and you do not need proof, before anyone will take you seriously.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They take exactly this, and they can tell you what your options are.

**{EMERGENCY.number}** — if you are ever in immediate danger.

I am not able to advise you on what to do about the money, the documents or the restrictions themselves — those steps can change the risk you are in, and a trained person needs to weigh that with you."""

COERCIVE_CONTROL_BN = f"""আপনি বলেছেন, সেজন্য ধন্যবাদ। আপনি যা বর্ণনা করছেন তার একটি নাম আছে: কারও টাকা, ফোন, কাগজপত্র বা তিনি কাজ করবেন কি না, পড়বেন কি না, বাইরে যাবেন কি না — এসব নিয়ন্ত্রণ করাকে **অর্থনৈতিক সহিংসতা ও কোয়ার্সিভ কন্ট্রোল (নিয়ন্ত্রণমূলক আচরণ)** হিসেবে স্বীকৃতি দেওয়া হয়। এটি জেন্ডারভিত্তিক সহিংসতারই একটি রূপ, এবং এটি বিয়ে বা সংসারের স্বাভাবিক অংশ নয়।

এই ধরনের সহিংসতার নাম দেওয়াই সবচেয়ে কঠিন, কারণ দেখানোর মতো কোনো আঘাত হয়তো নেই, আর আশপাশের মানুষ একে সাধারণ ব্যাপার বলে ধরে নিতে পারেন। কেউ আপনার কথা গুরুত্ব দিয়ে নেওয়ার আগে আপনাকে আঘাতও দেখাতে হবে না, প্রমাণও দিতে হবে না।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। ঠিক এ ধরনের বিষয়ই তাঁরা নেন এবং আপনার কী কী উপায় আছে তা বলতে পারেন।

**{EMERGENCY.number}** — আপনি যদি কখনো তাৎক্ষণিক বিপদে পড়েন।

টাকা, কাগজপত্র বা এই নিয়ন্ত্রণগুলো নিয়ে আপনি কী করবেন সে পরামর্শ আমি দিতে পারি না — এই পদক্ষেপগুলো আপনার ঝুঁকি বদলে দিতে পারে, আর একজন প্রশিক্ষিত মানুষকে আপনার সঙ্গে বসে সেটা বিবেচনা করতে হবে।"""

# --- Low distress ----------------------------------------------------------
#
# DRAFT WORDING — awaiting sign-off.
#
# "mon kharap." She has said she feels bad and has not said why. Three things
# this must do and two it must not.
#
#   sit with it first — the sentence she reads first should be about her, not
#     about what this app can do;
#   offer, do not prescribe — the corpus has grounding and coping material, and
#     she can have it by asking. Handing it over unasked answers a feeling with
#     a technique;
#   name one place with a human in it, once.
#
# It must NOT diagnose — no "that sounds like depression", no "you may be
# experiencing trauma" — and it must NOT ask what happened. If she wants to say,
# she will; being asked is what makes a person close the app.
#
# Kaan Pete Roi is named with its hours, for the same reason it is in the
# suicide script: a number that may not answer must never look like one that
# always does.
LOW_DISTRESS_EN = f"""I'm sorry you're feeling like this. You don't have to explain it or justify it to me.

If you'd like to talk to someone who will just listen, **{KAAN_PETE_ROI_NUMBER}** is Kaan Pete Roi, open {KAAN_PETE_ROI_HOURS_EN}.

And if it would help, you can ask me what WaterAid's material says about coping with stress or difficult feelings, and I'll answer from that. Or you can say more here — I'm listening."""

LOW_DISTRESS_BN = f"""আপনার এমন লাগছে শুনে খারাপ লাগল। কেন এমন লাগছে, তা আমাকে ব্যাখ্যা করতে হবে না।

কেউ শুধু আপনার কথা শুনুক — এমন চাইলে **{KAAN_PETE_ROI_NUMBER}** নম্বরে কান পেতে রই আছে, {KAAN_PETE_ROI_HOURS_BN} খোলা।

আর যদি কাজে লাগে, মানসিক চাপ বা কঠিন অনুভূতি নিয়ে ওয়াটারএইডের উপকরণ কী বলে তা জিজ্ঞেস করতে পারেন — আমি সেখান থেকে বলব। অথবা এখানেই আরও কিছু বলতে পারেন; আমি শুনছি।"""

# --- Vague input -----------------------------------------------------------
#
# "help", "ki korbo", "what should I do". ONE question back, and ONE safety
# line — not the referral block.
#
# The safety line is there because in THIS app a bare "help" is not the same
# input it would be in a shopping app. It may be someone who cannot yet type
# the sentence. So the reply does two things at once: it asks her to say a
# little more, and it makes sure that if she cannot, she still leaves this turn
# knowing one number. One number, not five, and framed as "if it is urgent" so
# that it does not read as a diagnosis of what she is going through.
VAGUE_EN = f"""I want to help — tell me a little more and I'll know where to start. What's happening, or what would you like to know about?

If it's urgent right now, don't wait for me: **{EMERGENCY.number}** reaches the police, fire service and ambulance, free, at any hour."""

VAGUE_BN = f"""আমি সাহায্য করতে চাই — একটু বিস্তারিত বললে কোথা থেকে শুরু করব বুঝতে পারব। কী ঘটছে, বা কোন বিষয়ে জানতে চান?

যদি এখনই জরুরি হয়, আমার জন্য অপেক্ষা করবেন না: **{EMERGENCY.number}** নম্বরে পুলিশ, ফায়ার সার্ভিস ও অ্যাম্বুলেন্স পাওয়া যায় — ফ্রি, যেকোনো সময়।"""

# --- Asking on behalf of someone else --------------------------------------
#
# DRAFT WORDING — awaiting sign-off.
#
# A different answer, not a weaker one. What she needs is not the disclosure
# text with the pronouns changed: she is not the one in danger, she is the one
# deciding what to do about somebody who is, and that has its own failure modes.
# The two worst are acting without the person's agreement, and going quiet
# because it feels like none of her business.
#
# So: believe her, tell her the three things that actually help, tell her the
# one thing not to do, and give her a number she can pass on or call herself.
# No advice on whether the other person should leave — that refusal applies
# whoever is asking.
THIRD_PARTY_EN = f"""It matters that you noticed, and that you're asking. People in this situation are often reached by a friend long before they reach a helpline.

What helps most is usually simple: believe her, tell her it isn't her fault, and stay in touch even if nothing changes for a long time. Let her decide what happens next, at her own pace — that includes deciding to do nothing for now.

What to avoid is acting for her: contacting the person harming her, reporting it without her agreement, or pressing her to leave. Each of those can raise the danger she is in, and it is her safety being spent.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. You can call for advice on supporting her, and so can she.

**{EMERGENCY.number}** — if she is in danger right now.

If she is under 18, {CHILD.number} is the Child Helpline, and this should not wait."""

THIRD_PARTY_BN = f"""আপনি লক্ষ করেছেন এবং জিজ্ঞেস করছেন — এটা গুরুত্বপূর্ণ। এ ধরনের পরিস্থিতিতে থাকা মানুষের কাছে হেল্পলাইনের অনেক আগে পৌঁছান একজন বন্ধু।

সবচেয়ে বেশি কাজে আসে সাধারণ কিছু বিষয়: তাঁকে বিশ্বাস করুন, বলুন যে এতে তাঁর কোনো দোষ নেই, আর অনেক দিন কিছু না বদলালেও যোগাযোগ রাখুন। এরপর কী হবে তা তিনিই ঠিক করবেন, তাঁর নিজের গতিতে — এর মধ্যে "এখন কিছুই করব না" সিদ্ধান্তটাও পড়ে।

যা এড়িয়ে চলবেন তা হলো তাঁর হয়ে সিদ্ধান্ত নেওয়া: যে ব্যক্তি ক্ষতি করছে তার সঙ্গে যোগাযোগ করা, তাঁর সম্মতি ছাড়া অভিযোগ জানানো, বা চলে যাওয়ার জন্য চাপ দেওয়া। এর প্রতিটিই তাঁর বিপদ বাড়াতে পারে, আর ঝুঁকিটা তাঁরই।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। তাঁকে কীভাবে পাশে থাকবেন সে বিষয়ে আপনি নিজেও পরামর্শ নিতে পারেন, তিনিও কল করতে পারেন।

**{EMERGENCY.number}** — তিনি যদি এখনই বিপদে থাকেন।

তাঁর বয়স ১৮ বছরের কম হলে {CHILD.number} শিশু হেল্পলাইন, এবং এটি ফেলে রাখার বিষয় নয়।"""

# --- Off topic -------------------------------------------------------------
#
# The light end of the tiered fallback. NO_CONTEXT below is written to rescue a
# real question this corpus happens to miss; it apologises, lists what it does
# have and gives two helplines. Sending all of that to "how do I cook rice" was
# absurd in the other direction — the app sounded like it could not tell a
# recipe from a crisis.
#
# api.py chooses between the two by how far the nearest chunk was, which is a
# number retrieval has already computed. Nothing about the gate changes.
OFF_TOPIC_EN = """That's outside what I know about — I only cover safeguarding and gender-based violence, and I'd rather say so than make something up.

Ask me anything in that area and I'll answer from WaterAid's own material."""

OFF_TOPIC_BN = """এই বিষয়ে আমি জানি না — আমি কেবল সেফগার্ডিং আর জেন্ডারভিত্তিক সহিংসতা নিয়ে কাজ করি, আর না জেনে কিছু বানিয়ে বলার চেয়ে সেটা স্বীকার করাই ভালো।

এই বিষয়ের যেকোনো প্রশ্ন করুন — ওয়াটারএইডের নিজস্ব উপকরণ থেকে উত্তর দেব।"""

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

# --- Referral blocks --------------------------------------------------------
#
# SAFETY DECIDES, THE AI SPEAKS. For every category except the five
# emergencies the model now writes the reply, and code appends one of these
# underneath. The fixed replies above are untouched and remain the fallback
# for a dead network, a missing key or a model failure — but they are no longer
# what a person reads when things are working.
#
# Each block is the fixed reply with the opening taken off: the contact lines,
# and the ONE sentence that states the limit ("this is the one thing I cannot
# advise on, and why"). No pleasantries, because the model has just written
# them, in her words, about her message.
#
# Two sizes. The FULL block is shown the first time a category's contacts
# appear in a conversation; the COMPACT block — one line — every time after,
# because the same helpline paragraph on every turn is the wall of text that
# made the app feel like a leaflet rack. The call buttons at the top of the
# screen are there the whole time regardless.
#
# Every number is interpolated from the one shared list. The model is
# forbidden from writing numbers precisely so that these are the only source.

_WATERAID_LINE_EN = (
    "If this involves a WaterAid programme, workplace, staff member or partner, "
    "you can also contact a safeguarding focal point under Important Numbers in "
    f"this app, or email {SAFEGUARDING_EMAIL}."
)
_WATERAID_LINE_BN = (
    "এটি যদি ওয়াটারএইডের কোনো কার্যক্রম, কর্মক্ষেত্র, কর্মী বা সহযোগী সংস্থার সঙ্গে "
    "সম্পর্কিত হয়, তাহলে এই অ্যাপের \"Important Numbers\"-এ দেওয়া সেফগার্ডিং ফোকাল "
    f"পয়েন্টের সঙ্গে যোগাযোগ করতে পারেন, অথবা ইমেইল করুন {SAFEGUARDING_EMAIL}।"
)
_VAWC_TOP_EN = f"**{VAWC.number}** at the top of the screen reaches a trained person, any time."
_VAWC_TOP_BN = f"উপরের **{VAWC.number}** বোতামে যেকোনো সময় একজন প্রশিক্ষিত মানুষকে পাওয়া যায়।"
_LEGAL_TOP_EN = f"**{VAWC.number}** at the top of the screen can refer you to free legal aid, any time."
_LEGAL_TOP_BN = f"উপরের **{VAWC.number}** বোতামে যেকোনো সময় বিনামূল্যে আইনি সহায়তার জন্য রেফার পাওয়া যায়।"

BLOCKS: dict[str, dict[str, dict[str, str]]] = {
    "personal_disclosure": {
        "en": {
            "full": f"""**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They take complaints of exactly this kind, including harassment at work, and can tell you what your options are.

**{EMERGENCY.number}** — if you are ever in immediate danger. If the person being harmed is under 18, {CHILD.number} is the Child Helpline.

{_WATERAID_LINE_EN}

I can't advise you on what to do next — the people on those numbers are trained for that, and they will take you seriously.""",
            "compact": _VAWC_TOP_EN,
        },
        "bn": {
            "full": f"""**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। কর্মক্ষেত্রে হয়রানিসহ ঠিক এ ধরনের অভিযোগই তাঁরা নেন এবং আপনার কী কী উপায় আছে তা বলতে পারেন।

**{EMERGENCY.number}** — আপনি যদি কখনো তাৎক্ষণিক বিপদে পড়েন। ক্ষতিগ্রস্ত ব্যক্তির বয়স ১৮ বছরের কম হলে {CHILD.number} শিশু হেল্পলাইন।

{_WATERAID_LINE_BN}

এরপর কী করবেন সে পরামর্শ আমি দিতে পারি না — উপরের নম্বরগুলোর মানুষ সেজন্য প্রশিক্ষিত, এবং তাঁরা আপনার কথা গুরুত্ব দিয়ে নেবেন।""",
            "compact": _VAWC_TOP_BN,
        },
    },
    "coercive_control": {
        "en": {
            "full": f"""**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They take exactly this, and they can tell you what your options are.

**{EMERGENCY.number}** — if you are ever in immediate danger.

I can't advise you on what to do about the money, the documents or the restrictions themselves — those steps can change the risk you are in, and a trained person needs to weigh that with you.""",
            "compact": _VAWC_TOP_EN,
        },
        "bn": {
            "full": f"""**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। ঠিক এ ধরনের বিষয়ই তাঁরা নেন এবং আপনার কী কী উপায় আছে তা বলতে পারেন।

**{EMERGENCY.number}** — আপনি যদি কখনো তাৎক্ষণিক বিপদে পড়েন।

টাকা, কাগজপত্র বা এই নিয়ন্ত্রণগুলো নিয়ে আপনি কী করবেন সে পরামর্শ আমি দিতে পারি না — এই পদক্ষেপগুলো আপনার ঝুঁকি বদলে দিতে পারে, আর একজন প্রশিক্ষিত মানুষকে আপনার সঙ্গে বসে সেটা বিবেচনা করতে হবে।""",
            "compact": _VAWC_TOP_BN,
        },
    },
    "low_distress": {
        "en": {
            "full": f"If you'd like to talk to someone who will just listen, **{KAAN_PETE_ROI_NUMBER}** is Kaan Pete Roi, open {KAAN_PETE_ROI_HOURS_EN}.",
            "compact": f"Kaan Pete Roi, **{KAAN_PETE_ROI_NUMBER}**, listens from {KAAN_PETE_ROI_HOURS_EN}.",
        },
        "bn": {
            "full": f"কেউ শুধু আপনার কথা শুনুক — এমন চাইলে **{KAAN_PETE_ROI_NUMBER}** নম্বরে কান পেতে রই আছে, {KAAN_PETE_ROI_HOURS_BN} খোলা।",
            "compact": f"কান পেতে রই, **{KAAN_PETE_ROI_NUMBER}** — {KAAN_PETE_ROI_HOURS_BN}।",
        },
    },
    "third_party_concern": {
        "en": {
            "full": f"""**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. You can call for advice on supporting her, and so can she.

**{EMERGENCY.number}** — if she is in danger right now.

If she is under 18, {CHILD.number} is the Child Helpline, and this should not wait.""",
            "compact": f"**{VAWC.number}** at the top of the screen reaches a trained person — for you or for her, any time.",
        },
        "bn": {
            "full": f"""**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। তাঁকে কীভাবে পাশে থাকবেন সে বিষয়ে আপনি নিজেও পরামর্শ নিতে পারেন, তিনিও কল করতে পারেন।

**{EMERGENCY.number}** — তিনি যদি এখনই বিপদে থাকেন।

তাঁর বয়স ১৮ বছরের কম হলে {CHILD.number} শিশু হেল্পলাইন, এবং এটি ফেলে রাখার বিষয় নয়।""",
            "compact": f"উপরের **{VAWC.number}** বোতামে যেকোনো সময় একজন প্রশিক্ষিত মানুষকে পাওয়া যায় — আপনার জন্য, তাঁর জন্যও।",
        },
    },
    "leave_decision": {
        "en": {
            "full": f"""Leaving is the most dangerous moment in an abusive situation, and the timing depends on details of your life that only a trained person talking with you can weigh — so whether or when to leave is the one thing I can't advise on.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. This is exactly what they are there to talk through, including safety planning.

**{EMERGENCY.number}** — if you are in danger right now.""",
            "compact": f"**{VAWC.number}** at the top of the screen can think this through with you safely, any time.",
        },
        "bn": {
            "full": f"""নির্যাতনের পরিস্থিতিতে চলে যাওয়ার সময়টাই সবচেয়ে বিপজ্জনক, এবং সঠিক সময় নির্ভর করে আপনার জীবনের এমন বিষয়গুলোর ওপর, যা কেবল আপনার সঙ্গে কথা বলে একজন প্রশিক্ষিত মানুষ বিবেচনা করতে পারেন — তাই চলে যাবেন কি না, কখন যাবেন, এই একটি বিষয়ে আমি পরামর্শ দিতে পারি না।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। নিরাপত্তা পরিকল্পনাসহ ঠিক এই বিষয়েই তাঁরা কথা বলেন।

**{EMERGENCY.number}** — আপনি যদি এখনই বিপদে থাকেন।""",
            "compact": f"উপরের **{VAWC.number}** বোতামে যেকোনো সময় একজন প্রশিক্ষিত মানুষ আপনার সঙ্গে নিরাপদে বিষয়টি ভাবতে পারেন।",
        },
    },
    "divorce_process": {
        "en": {
            "full": f"""In Bangladesh the process depends on which family law applies to you, and getting that wrong costs time and money you may not be able to spare — a lawyer can tell you in one conversation, which is why I won't guess at it.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They can refer you to free legal aid, and they can talk through your safety while it is happening.

**{EMERGENCY.number}** — if you are in danger at any point.""",
            "compact": _LEGAL_TOP_EN,
        },
        "bn": {
            "full": f"""বাংলাদেশে এই প্রক্রিয়া নির্ভর করে আপনার ক্ষেত্রে কোন পারিবারিক আইন প্রযোজ্য তার ওপর, আর সেটি ভুল হলে আপনার সময় ও অর্থ দুটোই নষ্ট হয় — একজন আইনজীবী এক বসাতেই তা বলে দিতে পারবেন, তাই আমি অনুমান করব না।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। তাঁরা বিনামূল্যে আইনি সহায়তায় রেফার করতে পারেন, এবং এই সময়টায় আপনার নিরাপত্তা নিয়েও কথা বলতে পারেন।

**{EMERGENCY.number}** — যেকোনো সময় বিপদে পড়লে।""",
            "compact": _LEGAL_TOP_BN,
        },
    },
    "economic_rights": {
        "en": {
            "full": f"""Denying a woman her inheritance or her property is recognised as **economic violence** — WaterAid's safeguarding material treats it as violence, not a private family dispute. What you are specifically entitled to depends on which family law applies to you, and a wrong answer could cost you a claim, so that part needs a lawyer.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential, and they can refer you to free legal aid.

You can also reach a safeguarding focal point through the Important Numbers page in this app.""",
            "compact": _LEGAL_TOP_EN,
        },
        "bn": {
            "full": f"""একজন নারীকে তাঁর উত্তরাধিকার বা সম্পত্তি থেকে বঞ্চিত করা **অর্থনৈতিক সহিংসতা** হিসেবে স্বীকৃত — ওয়াটারএইডের সেফগার্ডিং উপকরণে এটিকে সহিংসতা হিসেবেই দেখা হয়, পারিবারিক ব্যক্তিগত বিষয় হিসেবে নয়। ঠিক কতটা আপনার প্রাপ্য, তা নির্ভর করে আপনার ক্ষেত্রে কোন পারিবারিক আইন প্রযোজ্য তার ওপর, আর ভুল উত্তর আপনার দাবি নষ্ট করতে পারে — সেই অংশের জন্য একজন আইনজীবী দরকার।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়; তাঁরা বিনামূল্যে আইনি সহায়তায় রেফার করতে পারেন।

এই অ্যাপের "Important Numbers" পাতা থেকে সেফগার্ডিং ফোকাল পয়েন্টের সঙ্গেও যোগাযোগ করতে পারেন।""",
            "compact": _LEGAL_TOP_BN,
        },
    },
    "legal_advice": {
        "en": {
            "full": f"""I can't give legal advice or tell you how a case would turn out — I would only be guessing, and a wrong answer here costs you time you may not have.

**{VAWC.number}** — {VAWC.name_en}. They take complaints on domestic violence, child marriage, sexual harassment and dowry, and can refer you to legal aid.

A safeguarding focal point, listed under Important Numbers in this app, can also point you to legal support.""",
            "compact": _LEGAL_TOP_EN,
        },
        "bn": {
            "full": f"""আমি আইনি পরামর্শ দিতে পারি না, বা কোনো মামলার ফলাফল কী হবে তা বলতে পারি না — সেটা কেবল অনুমান হবে, আর এখানে ভুল উত্তর আপনার মূল্যবান সময় নষ্ট করবে।

**{VAWC.number}** — {VAWC.name_bn}। তাঁরা পারিবারিক সহিংসতা, বাল্যবিবাহ, যৌন হয়রানি ও যৌতুকের অভিযোগ নেন এবং আইনি সহায়তায় রেফার করতে পারেন।

সেফগার্ডিং ফোকাল পয়েন্ট (এই অ্যাপের "Important Numbers"-এ তালিকা আছে) আপনাকে আইনি সহায়তার দিকেও পথ দেখাতে পারেন।""",
            "compact": _LEGAL_TOP_BN,
        },
    },
    "medical_advice": {
        "en": {
            "full": f"""I can't tell you how to treat an injury — getting that wrong causes real harm, and I am not able to see or assess it.

**{EMERGENCY.number}** — for an ambulance, or if the injury is serious. Free, any hour. For anything that needs looking at, the emergency department of your nearest hospital is the right place, and treatment there does not depend on explaining how it happened.

**{VAWC.number}** — {VAWC.name_en}. If the injury came from someone hurting you, they can arrange medical care through a One-Stop Crisis Centre and talk through what happens next. Free, 24 hours, confidential.""",
            "compact": f"**{EMERGENCY.number}** at the top of the screen for an ambulance; **{VAWC.number}** if someone hurt you.",
        },
        "bn": {
            "full": f"""কোনো আঘাতের চিকিৎসা কীভাবে করবেন তা আমি বলতে পারি না — এতে ভুল হলে প্রকৃত ক্ষতি হয়, আর আমি আঘাতটি দেখতে বা বুঝতে পারি না।

**{EMERGENCY.number}** — অ্যাম্বুলেন্সের জন্য, বা আঘাত গুরুতর হলে। ফ্রি, যেকোনো সময়। যা দেখানো দরকার, তার জন্য নিকটস্থ হাসপাতালের জরুরি বিভাগই সঠিক জায়গা; সেখানে চিকিৎসা পেতে কীভাবে আঘাত পেয়েছেন তা ব্যাখ্যা করা বাধ্যতামূলক নয়।

**{VAWC.number}** — {VAWC.name_bn}। আঘাতটি যদি কেউ আপনাকে আঘাত করার কারণে হয়ে থাকে, তাঁরা ওয়ান-স্টপ ক্রাইসিস সেন্টারের মাধ্যমে চিকিৎসার ব্যবস্থা করতে এবং পরবর্তী করণীয় নিয়ে কথা বলতে পারেন। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।""",
            "compact": f"অ্যাম্বুলেন্সের জন্য উপরের **{EMERGENCY.number}**; কেউ আঘাত করে থাকলে **{VAWC.number}**।",
        },
    },
    "confront_or_evidence": {
        "en": {
            "full": f"""I won't suggest ways to confront, reason with, record, or collect evidence against someone who is harming you — those steps often raise the danger, and if they are ever the right move, a trained person should plan them with you.

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential.

**{EMERGENCY.number}** — if you are in danger right now.""",
            "compact": f"**{VAWC.number}** at the top of the screen can plan any next step with you safely, any time.",
        },
        "bn": {
            "full": f"""যে মানুষটি আপনার ক্ষতি করছে, তার মুখোমুখি হওয়া, তাকে বোঝানো, তার কথা রেকর্ড করা বা তার বিরুদ্ধে প্রমাণ সংগ্রহ করার কোনো উপায় আমি বলব না — এই পদক্ষেপগুলো প্রায়ই বিপদ বাড়ায়; আর কখনো যদি তা প্রয়োজন হয়, একজন প্রশিক্ষিত মানুষ আপনার সঙ্গে পরিকল্পনা করে সেটা ঠিক করবেন।

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়।

**{EMERGENCY.number}** — আপনি যদি এখনই বিপদে থাকেন।""",
            "compact": f"উপরের **{VAWC.number}** বোতামে একজন প্রশিক্ষিত মানুষ যেকোনো পরবর্তী পদক্ষেপ আপনার সঙ্গে নিরাপদে পরিকল্পনা করতে পারেন।",
        },
    },
    "reporting_request": {
        "en": {
            "full": f"""I can't take a report — nothing typed here is passed on to anyone. Where a report actually reaches a person:

**{VAWC.number}** — {VAWC.name_en}. Free, 24 hours, confidential. They take complaints of violence, abuse and harassment directly, and can refer you on.

**{EMERGENCY.number}** — the police, if a crime has been committed or anyone is in danger now.

If this concerns a WaterAid programme, workplace, staff member or partner, it goes to safeguarding: email {SAFEGUARDING_EMAIL}, or use the contacts under Important Numbers in this app. If the person harmed is under 18, {CHILD.number} is the Child Helpline.

Whether to report, and when, is your decision.""",
            "compact": f"To report to a person: **{VAWC.number}** at the top of the screen, any time; **{EMERGENCY.number}** for the police.",
        },
        "bn": {
            "full": f"""আমি কোনো অভিযোগ গ্রহণ করতে পারি না — এখানে যা লেখা হয় তা কারও কাছে পাঠানো হয় না। অভিযোগ আসলে যেখানে একজন মানুষের কাছে পৌঁছায়:

**{VAWC.number}** — {VAWC.name_bn}। ফ্রি, ২৪ ঘণ্টা, গোপনীয়। সহিংসতা, নির্যাতন ও হয়রানির অভিযোগ তাঁরা সরাসরি নেন এবং প্রয়োজনে অন্যত্র পাঠাতে পারেন।

**{EMERGENCY.number}** — পুলিশ, যদি কোনো অপরাধ ঘটে থাকে বা কেউ এখনই বিপদে থাকেন।

বিষয়টি যদি ওয়াটারএইডের কোনো কার্যক্রম, কর্মক্ষেত্র, কর্মী বা সহযোগী সংস্থার সঙ্গে সম্পর্কিত হয়, তাহলে সেটি সেফগার্ডিংয়ের বিষয়: ইমেইল করুন {SAFEGUARDING_EMAIL}, অথবা এই অ্যাপের "Important Numbers"-এ দেওয়া যোগাযোগ ব্যবহার করুন। ক্ষতিগ্রস্ত ব্যক্তির বয়স ১৮ বছরের কম হলে {CHILD.number} শিশু হেল্পলাইন।

অভিযোগ করবেন কি না, আর কখন করবেন — সিদ্ধান্তটি আপনার।""",
            "compact": f"একজন মানুষের কাছে অভিযোগ জানাতে: উপরের **{VAWC.number}**, যেকোনো সময়; পুলিশের জন্য **{EMERGENCY.number}**।",
        },
    },
}

# Categories that get NO block: the model's words stand alone. Social turns,
# because "You're welcome" followed by a helpline paragraph is the old problem
# in miniature; identity and privacy, because their facts are stated in the
# model's own reply from a fixed note and there is nothing to append; the
# emergencies, because they never reach the model at all.
NO_BLOCK = frozenset(
    {"greeting", "thanks", "acknowledgement", "bot_abuse", "vague", "identity", "privacy"}
)


def has_block(category: str | None) -> bool:
    return category is not None and category in BLOCKS


def referral_block(category: str, language: str, mode: str) -> str:
    """The block appended under a model-written reply.

    `mode` is "full" the first time this category's contacts appear in a
    conversation and "compact" after that — sessions.py keeps the score.
    """
    if mode not in ("full", "compact"):
        raise ValueError(f"block mode must be full or compact, not {mode!r}")
    by_language = BLOCKS[category]
    return by_language.get(text_language(language), by_language["en"])[mode]


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
    "medical_advice": {"en": REFUSE_MEDICAL_EN, "bn": REFUSE_MEDICAL_BN},
    "confront_or_evidence": {"en": REFUSE_CONFRONT_EN, "bn": REFUSE_CONFRONT_BN},
    "no_context": {"en": NO_CONTEXT_EN, "bn": NO_CONTEXT_BN},
    "off_topic": {"en": OFF_TOPIC_EN, "bn": OFF_TOPIC_BN},
    "personal_disclosure": {"en": DISCLOSURE_EN, "bn": DISCLOSURE_BN},
    "coercive_control": {"en": COERCIVE_CONTROL_EN, "bn": COERCIVE_CONTROL_BN},
    "reporting_request": {"en": REPORTING_EN, "bn": REPORTING_BN},
    "third_party_concern": {"en": THIRD_PARTY_EN, "bn": THIRD_PARTY_BN},
    "low_distress": {"en": LOW_DISTRESS_EN, "bn": LOW_DISTRESS_BN},
    "greeting": {"en": GREETING_EN, "bn": GREETING_BN},
    "greeting_salam": {"en": GREETING_SALAM_EN, "bn": GREETING_SALAM_BN},
    "greeting_namaskar": {"en": GREETING_NAMASKAR_EN, "bn": GREETING_NAMASKAR_BN},
    "thanks": {"en": THANKS_EN, "bn": THANKS_BN},
    "acknowledgement": {"en": ACKNOWLEDGEMENT_EN, "bn": ACKNOWLEDGEMENT_BN},
    "identity": {"en": IDENTITY_EN, "bn": IDENTITY_BN},
    "privacy": {"en": PRIVACY_EN, "bn": PRIVACY_BN},
    "bot_abuse": {"en": BOT_ABUSE_EN, "bn": BOT_ABUSE_BN},
    "vague": {"en": VAGUE_EN, "bn": VAGUE_BN},
    "unreachable": {"en": UNREACHABLE_EN, "bn": UNREACHABLE_BN},
    "starting": {"en": STARTING_EN, "bn": STARTING_BN},
    "rate_limited": {"en": RATE_LIMITED_EN, "bn": RATE_LIMITED_BN},
}


# Every category safety.py can return must have text here, and the place to
# find that out is import time — not in front of a user, mid-turn, as a KeyError
# where a phone number should have been.
def _check_every_category_has_text() -> None:  # pragma: no cover - import guard
    import safety

    missing = [c for c in safety._PRIORITY if c not in RESPONSES]
    if missing:
        raise RuntimeError(f"safety categories with no referral text: {missing}")

    # Every category the model answers must either have a block or be
    # explicitly listed as needing none. A category that is neither is one
    # somebody added without deciding what goes under the reply — and the
    # default of "nothing" is the wrong default for a safety category.
    undecided = [
        c for c in safety._PRIORITY
        if c not in safety.DEVICE_CATEGORIES and c not in BLOCKS and c not in NO_BLOCK
    ]
    if undecided:
        raise RuntimeError(
            f"categories with neither a referral block nor a NO_BLOCK entry: {undecided}"
        )
    unknown = [c for c in BLOCKS if c not in safety._PRIORITY]
    if unknown:
        raise RuntimeError(f"referral blocks for categories that do not exist: {unknown}")


_check_every_category_has_text()


def text_language(language: str) -> str:
    """Which side of a bilingual pair to read.

    Romanised Bangla gets the Bangla text: a person who typed "amar shami
    amake mare" reads Bangla and typed it in Latin letters because that is
    what her keyboard offered. Answering her in English was the wrong call
    for as long as it lasted.
    """
    return "en" if language == "en" else "bn"


def response_for(category: str, language: str) -> str:
    """The hardcoded reply for a category, in 'en', 'bn' or 'bn_roman'."""
    try:
        by_language = RESPONSES[category]
    except KeyError:  # pragma: no cover - guards a typo at import time
        raise KeyError(f"no hardcoded response for category {category!r}") from None
    return by_language.get(text_language(language), by_language["en"])
