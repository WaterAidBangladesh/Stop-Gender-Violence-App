# Referral verification list

Generated 2026-09-28 by `tools/verification_list.py` from `app/referrals.py`. Do not edit by hand — re-run it.

## Why this exists

Bharosha is a referral system. Every safety reply it gives ends in one of these numbers, and none of them has been dialled by a person. If a number is wrong the app does not fail neutrally: it sends someone somewhere useless at the worst moment of her life, and she concludes that help does not work.

16430 was in this app as the GBV helpline after it had already been replaced. It was caught by a document, not by testing.

## How to verify

**Ringing is not a pass.** For each number, confirm every claim listed under it. Those claims are what the app tells people, so they are what has to be true. Where a claim turns out to be wrong, the fix is to change `app/referrals.py` — not to leave the number in with the wrong description.

Call from a mobile on a normal network, not a landline or VoIP. Note the date and the time of day, because several of these claim 24-hour service and the failure mode is usually at night.

## National helplines

### 999 — National Emergency Services — police, fire, ambulance

- **In crisis scripts:** yes
- **Shown in the app as:** Free, 24 hours. Connects you to police, fire and ambulance anywhere in the country. Use this if anyone is in danger now.

Confirm:

- [ ] Answers 24 hours
- [ ] Free to call from any network
- [ ] Reaches police, fire AND ambulance from this one number
- [ ] Operator can dispatch to a caller's location

| result | |
|---|---|
| Answered? | |
| Date and time called | |
| Who answered, and what they said the service is | |
| Claims that were WRONG | |

### 109 — National Helpline for Violence Against Women and Children

- **In crisis scripts:** yes
- **Shown in the app as:** Free, 24 hours, confidential. Takes complaints of violence, abuse and harassment, including at work. Offers counselling and legal information, and can refer you to protection and social services.

Confirm:

- [ ] Answers 24 hours
- [ ] Free to call from any network
- [ ] Confidential — ask explicitly what is recorded and who can see it
- [ ] Takes complaints of violence, abuse and harassment directly
- [ ] Takes WORKPLACE harassment specifically (the disclosure script says so)
- [ ] Can trace a caller's location and send local police — this is claimed in the emergency script, so confirm it is still true
- [ ] Can refer on to protection and social services

| result | |
|---|---|
| Answered? | |
| Date and time called | |
| Who answered, and what they said the service is | |
| Claims that were WRONG | |

### 16263 — Shastho Batayon — national health call centre (medical advice, ambulance)

- **In crisis scripts:** NO — deliberately excluded
- **Shown in the app as:** Free, 24 hours. Medical advice from doctors, health information and emergency ambulance, run by the Directorate General of Health Services. This is a HEALTH line, not a gender-based violence line — for violence, call 109 or 999.

Confirm:

- [ ] Answers 24 hours
- [ ] Free to call
- [ ] Is Shastho Batayon, the DGHS health line — NOT a GBV service
- [ ] Gives medical advice from a doctor and can send an ambulance
- [ ] URGENT: press reports say staff have gone unpaid and closure was threatened. Confirm the service is actually operating.

| result | |
|---|---|
| Answered? | |
| Date and time called | |
| Who answered, and what they said the service is | |
| Claims that were WRONG | |

### 1098 — Child Helpline

- **In crisis scripts:** yes
- **Shown in the app as:** Free, 24 hours, confidential. For children facing abuse, violence, exploitation, neglect or child marriage. Connects children with protection services and emergency help.

Confirm:

- [ ] Answers 24 hours
- [ ] Free to call
- [ ] Confidential
- [ ] Takes reports about a child from an ADULT, not only from children
- [ ] Covers child marriage, not only physical abuse

| result | |
|---|---|
| Answered? | |
| Date and time called | |
| Who answered, and what they said the service is | |
| Claims that were WRONG | |

### 333 — Citizen Service

- **In crisis scripts:** yes
- **Shown in the app as:** Government information line for public services, complaints and social issues, including help reaching local officials.

Confirm:

- [ ] Answers 24 hours
- [ ] Cost to call — confirm whether it is free
- [ ] Can direct a caller to local officials

| result | |
|---|---|
| Answered? | |
| Date and time called | |
| Who answered, and what they said the service is | |
| Claims that were WRONG | |

### 09612-119911 — Kaan Pete Roi

- **In crisis scripts:** yes — the suicide-risk reply, after 999
- **Hours claimed:** 3pm to 3am

Confirm:

- [ ] Answers during 3pm to 3am — and NOT outside them
- [ ] Emotional support from trained volunteers
- [ ] Is an ordinary mobile number, so normal call charges apply. The suicide script says this, so confirm it is still a mobile number.
- [ ] What happens OUTSIDE those hours: ringing with no answer, a recorded message, or a diverted line? Someone in crisis will find out at 4am.

| result | |
|---|---|
| Answered in hours? | |
| Answered OUT of hours? (call after 3am) | |
| Date and time called | |
| Claims that were WRONG | |

## Safeguarding focal points

These are organisation staff, not helplines. Bharosha names them in the disclosure and reporting replies, via the app's Important Numbers screen. Confirm the person still holds the safeguarding role and that the inbox is monitored — a focal point who has left the organisation is the same failure as a dead number.

| Organisation | Number | Email | Rings? | Right person? | Inbox monitored? |
|---|---|---|---|---|---|
| Dushtha Shasthya Kendra (DSK) | 01717070777 | psea@dskbangladesh.org | | | |
| Village Education Resource Center (VERC) | 01716896162 | vercpsea@vercbd.org | | | |
| Rupantar | 01763568402 | ananna@rupantar.org | | | |
| Eco-Social Development Organization (ESDO) | 01713149304 | esdo.safeguarding2021@gmail.com | | | |
| Sajida Foundation | 01777771515 | shec@sajidafoundation.org | | | |
| Nabolok | 01711965593 | setunabolok@gmail.com | | | |
| Bhumijo | 01717305141 | farhana.r@bhumijo.com | | | |
| SKS Foundation | 01713484599 | ummequlsumila@sks-bd.org | | | |
| BASA Foundation | 01730044916 | sabrina.basa.safeguard@gmail.com | | | |

### safeguardwab@wateraid.org

The WaterAid Bangladesh safeguarding inbox, named in the disclosure and reporting replies. Confirm it accepts external mail, that someone reads it, and that there is a stated response time.

- [ ] Test email sent and acknowledged

## Until this comes back

`app/referrals.py` carries `VERIFICATION_STATUS`, which the test suite checks. It says UNVERIFIED. Change it only when this document comes back completed.
