"""
Seed script for populating the knowledge base with GST rules and sections.

Run with: python -m scripts.seed_knowledge_base
"""

import asyncio
import hashlib
from uuid import uuid4
from datetime import date
from typing import List, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_engine, get_session_maker, init_db
from app.core.config import settings

# OpenAI for embeddings
from openai import AsyncOpenAI


# GST Sections commonly referenced in notices
GST_SECTIONS = [
    {
        "reference": "Section 9",
        "title": "Levy and Collection of Tax",
        "source_type": "gst_section",
        "content": """Section 9 of the CGST Act, 2017 - Levy and Collection of Tax

(1) Subject to the provisions of sub-section (2), there shall be levied a tax called the central goods and services tax on all intra-State supplies of goods or services or both, except on the supply of alcoholic liquor for human consumption, on the value determined under section 15 and at such rates, not exceeding twenty per cent., as may be notified by the Government on the recommendations of the Council.

(2) The central tax on the supply of petroleum crude, high speed diesel, motor spirit (commonly known as petrol), natural gas and aviation turbine fuel shall be levied with effect from such date as may be notified by the Government on the recommendations of the Council.

(3) The Government may, on the recommendations of the Council, by notification, specify categories of supply of goods or services or both, the tax on which shall be paid on reverse charge basis by the recipient of such goods or services or both.

(4) The central tax in respect of the supply of taxable goods or services or both by a supplier, who is not registered, to a registered person shall be paid by such person on reverse charge basis as the recipient.

Key Points:
- CGST is levied on all intra-state supplies
- Maximum rate is 20%
- Reverse charge mechanism applies in specified cases
- Petroleum products excluded until notified""",
        "summary": "Establishes the levy of CGST on intra-state supplies at rates up to 20%, with provisions for reverse charge mechanism.",
        "keywords": ["levy", "collection", "CGST", "intra-state", "reverse charge", "tax rate"],
        "categories": ["tax_levy", "basic_provisions"],
        "related_sections": ["Section 5 IGST", "Section 7", "Section 15"],
    },
    {
        "reference": "Section 16",
        "title": "Eligibility and Conditions for Taking Input Tax Credit",
        "source_type": "gst_section",
        "content": """Section 16 of the CGST Act, 2017 - Eligibility and Conditions for Taking Input Tax Credit

(1) Every registered person shall, subject to such conditions and restrictions as may be prescribed and in the manner specified in section 49, be entitled to take credit of input tax charged on any supply of goods or services or both to him which are used or intended to be used in the course or furtherance of his business.

(2) Notwithstanding anything contained in this section, no registered person shall be entitled to the credit of any input tax in respect of any supply of goods or services or both to him unless:
(a) he is in possession of a tax invoice or debit note issued by a supplier registered under this Act
(b) he has received the goods or services or both
(ba) the details of the invoice or debit note have been furnished by the supplier in GSTR-1 and communicated to the recipient
(c) subject to the provisions of section 41, the tax charged has actually been paid to the Government
(d) he has furnished the return under section 39

(3) Where the registered person has claimed depreciation on the tax component of the cost of capital goods, the input tax credit shall not be allowed.

(4) A registered person shall not be entitled to take input tax credit after the 30th day of November following the end of financial year to which such invoice pertains or furnishing of the relevant annual return, whichever is earlier.

Key Points:
- ITC available for business use only
- Four conditions must be met: tax invoice, receipt of goods/services, supplier filing, and payment
- Time limit: 30th November of following FY or annual return date
- No ITC if depreciation claimed on tax component""",
        "summary": "Specifies eligibility conditions for claiming Input Tax Credit including possession of invoice, receipt of goods/services, and time limits.",
        "keywords": ["ITC", "input tax credit", "eligibility", "conditions", "tax invoice", "GSTR-1"],
        "categories": ["input_tax_credit", "compliance"],
        "related_sections": ["Section 17", "Section 18", "Section 41", "Section 49"],
    },
    {
        "reference": "Section 17",
        "title": "Apportionment of Credit and Blocked Credits",
        "source_type": "gst_section",
        "content": """Section 17 of the CGST Act, 2017 - Apportionment of Credit and Blocked Credits

(1) Where the goods or services or both are used partly for business and partly for other purposes, the amount of credit shall be restricted to so much of the input tax as is attributable to the purposes of business.

(2) Where the goods or services or both are used partly for effecting taxable supplies and partly for exempt supplies, the amount of credit shall be restricted to so much of the input tax as is attributable to taxable supplies.

(5) Notwithstanding anything contained in sub-section (1) and (2), input tax credit shall NOT be available in respect of the following:
(a) motor vehicles and conveyances (with exceptions)
(b) food and beverages, outdoor catering, beauty treatment, health services, cosmetic and plastic surgery (with exceptions)
(c) membership of a club, health and fitness centre
(d) rent-a-cab, life insurance and health insurance (with exceptions)
(e) travel benefits extended to employees on vacation
(f) works contract services for construction of immovable property
(g) goods or services for construction of immovable property on own account
(h) goods or services on which tax has been paid under composition scheme
(i) goods or services used for personal consumption
(j) goods lost, stolen, destroyed, written off or disposed of by way of gift or free samples
(k) tax paid under sections 74, 129 and 130

Key Points:
- ITC must be apportioned for mixed use (business/personal, taxable/exempt)
- Blocked credits include motor vehicles, food, club membership, construction
- Personal consumption items are blocked
- Composition scheme purchases have no ITC""",
        "summary": "Defines apportionment rules for ITC and lists blocked credits including motor vehicles, food, construction, and personal consumption.",
        "keywords": ["blocked credit", "apportionment", "motor vehicles", "construction", "personal consumption"],
        "categories": ["input_tax_credit", "blocked_credits"],
        "related_sections": ["Section 16", "Section 18", "Rule 42", "Rule 43"],
    },
    {
        "reference": "Section 29",
        "title": "Cancellation of Registration",
        "source_type": "gst_section",
        "content": """Section 29 of the CGST Act, 2017 - Cancellation of Registration

(1) The proper officer may, either on his own motion or on an application filed by the registered person or by his legal heirs, cancel the registration, in such manner and within such period as may be prescribed, having regard to the circumstances where:
(a) the business has been discontinued, transferred, amalgamated or demerged
(b) there is any change in the constitution of the business
(c) the taxable person is no longer liable to be registered under section 22 or section 24

(2) The proper officer may cancel the registration of a person from such date, including any retrospective date, as he may deem fit, where:
(a) a registered person has contravened the provisions of the Act or rules
(b) a person paying tax under composition scheme has not furnished returns for three consecutive tax periods
(c) any registered person, other than composition, has not furnished returns for a continuous period of six months
(d) any person who has taken voluntary registration has not commenced business within six months
(e) registration has been obtained by fraud, wilful misstatement or suppression of facts

(3) The cancellation under sub-section (2) shall be preceded by issuance of show cause notice in FORM GST REG-17 and providing opportunity of being heard.

(4) The cancellation shall not affect the liability of the person to pay tax and other dues or to discharge any obligation under this Act.

(5) Upon cancellation, the registered person shall pay an amount equal to ITC on inputs held in stock, semi-finished goods, finished goods, or capital goods on the day immediately preceding the date of cancellation.

Key Points:
- Can be voluntary or suo moto by officer
- Non-filing of returns for 6 months (regular) or 3 periods (composition) triggers cancellation
- Show cause notice (REG-17) must be issued
- ITC reversal required on cancellation""",
        "summary": "Outlines grounds for cancellation of GST registration including non-filing of returns, and requires ITC reversal upon cancellation.",
        "keywords": ["cancellation", "registration", "REG-17", "non-filing", "ITC reversal"],
        "categories": ["registration", "compliance"],
        "related_sections": ["Section 22", "Section 24", "Section 30"],
    },
    {
        "reference": "Section 50",
        "title": "Interest on Delayed Payment of Tax",
        "source_type": "gst_section",
        "content": """Section 50 of the CGST Act, 2017 - Interest on Delayed Payment of Tax

(1) Every person who is liable to pay tax in accordance with the provisions of this Act or the rules made thereunder, but fails to pay the tax or any part thereof to the Government within the period prescribed, shall for the period for which the tax or any part thereof remains unpaid, pay, on his own, interest at such rate, not exceeding eighteen per cent., as may be notified by the Government on the recommendations of the Council.

(2) The interest under sub-section (1) shall be calculated, in such manner as may be prescribed, from the day succeeding the day on which such tax was due to be paid.

(3) A taxable person who makes an undue or excess claim of input tax credit under sub-section (10) of section 42 or undue or excess reduction in output tax liability under sub-section (10) of section 43, shall pay interest on such undue or excess claim or on such undue or excess reduction, as the case may be, at such rate not exceeding twenty-four per cent., as may be notified by the Government on the recommendations of the Council.

Current Interest Rates (as notified):
- Delayed payment of tax: 18% per annum
- Undue/excess ITC claim: 24% per annum

Key Points:
- Interest is automatic and must be paid by taxpayer
- Rate is 18% for delayed tax payment
- Rate is 24% for wrongful ITC claims
- Calculated from due date until payment""",
        "summary": "Prescribes interest rates for delayed tax payment (18%) and wrongful ITC claims (24%), calculated from due date.",
        "keywords": ["interest", "delayed payment", "18%", "24%", "ITC excess"],
        "categories": ["interest", "penalties", "compliance"],
        "related_sections": ["Section 42", "Section 43", "Section 73", "Section 74"],
    },
    {
        "reference": "Section 61",
        "title": "Scrutiny of Returns",
        "source_type": "gst_section",
        "content": """Section 61 of the CGST Act, 2017 - Scrutiny of Returns

(1) The proper officer may scrutinize the return and related particulars furnished by the registered person to verify the correctness of the return and inform him of the discrepancies noticed, if any, in such manner as may be prescribed and seek his explanation thereto.

(2) In case the explanation is found acceptable, the registered person shall be informed accordingly and no further action shall be taken in this regard.

(3) In case no satisfactory explanation is furnished within a period of thirty days of being informed or such further period as may be permitted by the proper officer or where the registered person, after accepting the discrepancies, fails to take the corrective measure in his return for the month in which the discrepancy is accepted, the proper officer may initiate appropriate action including those under section 65 or section 66 or section 67, or proceed to determine the tax and other dues under section 73 or section 74.

Form Used: ASMT-10 (Scrutiny Notice)
Response Form: ASMT-11

Key Points:
- Returns can be scrutinized for correctness
- Discrepancies communicated via ASMT-10
- 30 days given for explanation
- If unsatisfied, can lead to audit (Section 65/66) or demand proceedings (Section 73/74)""",
        "summary": "Enables scrutiny of returns via ASMT-10 notice with 30 days for response, potentially leading to audit or demand proceedings.",
        "keywords": ["scrutiny", "ASMT-10", "discrepancy", "returns", "verification"],
        "categories": ["assessment", "scrutiny", "compliance"],
        "related_sections": ["Section 65", "Section 66", "Section 73", "Section 74"],
    },
    {
        "reference": "Section 65",
        "title": "Audit by Tax Authorities",
        "source_type": "gst_section",
        "content": """Section 65 of the CGST Act, 2017 - Audit by Tax Authorities

(1) The Commissioner or any officer authorised by him, by way of a general or a specific order, may undertake audit of any registered person for such period, at such frequency and in such manner as may be prescribed.

(2) The officers referred to in sub-section (1) may conduct audit at the place of business of the registered person or in their office.

(3) The registered person shall be informed by way of a notice not less than fifteen working days prior to the conduct of audit in such manner as may be prescribed.

(4) The audit shall be completed within a period of three months from the date of commencement of the audit.

(5) During the course of audit, the authorised officer may require the registered person to afford him the necessary facility to verify the books of account or other documents as he may require and to furnish such information as he may require and render assistance for timely completion of the audit.

(6) On conclusion of audit, the proper officer shall inform the registered person, within thirty days, about the findings, the rights and obligations of such person and the reasons for such findings.

(7) Where the audit results in detection of tax not paid or short paid or erroneously refunded, or input tax credit wrongly availed or utilised, the proper officer may initiate action under section 73 or section 74.

Form Used: ADT-01 (Audit Notice)

Key Points:
- 15 days advance notice required (ADT-01)
- Audit must complete within 3 months
- Findings communicated within 30 days
- Can lead to demand proceedings under Section 73/74""",
        "summary": "Authorizes tax audit with 15 days notice via ADT-01, completion within 3 months, and potential demand proceedings.",
        "keywords": ["audit", "ADT-01", "tax authorities", "books of account", "inspection"],
        "categories": ["audit", "compliance", "assessment"],
        "related_sections": ["Section 66", "Section 67", "Section 73", "Section 74"],
    },
    {
        "reference": "Section 73",
        "title": "Determination of Tax Not Paid or Short Paid - Non-Fraud Cases",
        "source_type": "gst_section",
        "content": """Section 73 of the CGST Act, 2017 - Determination of Tax Not Paid or Short Paid or Erroneously Refunded or Input Tax Credit Wrongly Availed or Utilised for Any Reason Other Than Fraud or Wilful Misstatement or Suppression of Facts

(1) Where it appears to the proper officer that any tax has not been paid or short paid or erroneously refunded, or where input tax credit has been wrongly availed or utilised for any reason, other than fraud or wilful misstatement or suppression of facts to evade tax, he shall serve notice on the person chargeable with tax requiring him to show cause as to why he should not pay the amount specified in the notice along with interest and penalty.

(2) The proper officer shall issue the notice at least three months prior to the time limit specified in sub-section (10) for issuance of order.

(5) The person chargeable with tax may, before service of notice or within thirty days of issue of notice, pay the amount of tax along with interest at the rate specified under sub-section (1) of section 50 and a penalty equal to fifteen per cent of such tax on the basis of his own ascertainment or as ascertained by the officer and inform the proper officer, who shall not serve any notice or issue any order.

(6) Where a person has paid the tax under sub-section (5), the proceedings shall be deemed to be concluded.

(9) The proper officer shall, after considering the representation, if any, made by person, determine the amount of tax, interest and penalty due and issue an order.

(10) The order shall be issued within three years from the due date for furnishing of annual return for the financial year to which the demand relates.

(11) Penalty shall be ten per cent of the tax or Rs. 10,000, whichever is higher.

Form Used: DRC-01 (Show Cause Notice)
Order Form: DRC-07

Key Points:
- For non-fraud cases (no suppression, misstatement)
- Notice (DRC-01) must be 3 months before time limit
- Can pay tax + 15% penalty before notice to close
- Time limit: 3 years from annual return due date
- Penalty: 10% of tax or Rs. 10,000""",
        "summary": "Procedure for tax demand in non-fraud cases via DRC-01, with 3-year time limit, 15% pre-notice settlement, and 10% penalty.",
        "keywords": ["DRC-01", "demand", "non-fraud", "short paid", "ITC wrongly availed", "penalty"],
        "categories": ["demand", "assessment", "penalty"],
        "related_sections": ["Section 74", "Section 75", "Section 50"],
    },
    {
        "reference": "Section 74",
        "title": "Determination of Tax - Fraud Cases",
        "source_type": "gst_section",
        "content": """Section 74 of the CGST Act, 2017 - Determination of Tax Not Paid or Short Paid or Erroneously Refunded or Input Tax Credit Wrongly Availed or Utilised by Reason of Fraud or Wilful Misstatement or Suppression of Facts

(1) Where it appears to the proper officer that any tax has not been paid or short paid or erroneously refunded, or where input tax credit has been wrongly availed or utilised by reason of fraud, or any wilful misstatement or suppression of facts to evade tax, he shall serve notice on the person chargeable with tax requiring him to show cause as to why he should not pay the amount specified in the notice along with interest and penalty.

(2) The proper officer shall issue notice at least six months prior to the time limit for issuance of order.

(5) The person may, before service of notice, pay the amount of tax along with interest and penalty equivalent to fifteen per cent of such tax and inform the officer, who shall not serve any notice.

(6) Where the person pays tax along with interest and penalty equivalent to twenty-five per cent within thirty days of issue of notice, no further proceedings shall be initiated.

(7) Where any appellate authority or tribunal or court concludes that notice was not warranted under this section, the penalty paid shall be refunded with interest.

(10) The proper officer shall issue order within five years from the due date for furnishing of annual return for the financial year to which the demand relates.

(11) Penalty shall be equivalent to the tax determined (100% penalty).

Form Used: DRC-01 (Show Cause Notice)
Order Form: DRC-07

Key Points:
- For fraud, wilful misstatement, or suppression
- Notice 6 months before time limit
- Pay tax + 15% before notice to avoid proceedings
- Pay tax + 25% within 30 days of notice to close
- Time limit: 5 years from annual return due date
- Penalty: 100% of tax (equal to tax amount)""",
        "summary": "Procedure for fraud cases via DRC-01, with 5-year time limit, 15%/25% settlement options, and 100% penalty.",
        "keywords": ["DRC-01", "fraud", "suppression", "wilful misstatement", "100% penalty"],
        "categories": ["demand", "fraud", "penalty", "assessment"],
        "related_sections": ["Section 73", "Section 75", "Section 122"],
    },
    {
        "reference": "Section 122",
        "title": "Penalty for Certain Offences",
        "source_type": "gst_section",
        "content": """Section 122 of the CGST Act, 2017 - Penalty for Certain Offences

(1) Where a taxable person who:
(i) supplies goods or services without issue of invoice or issues incorrect invoice
(ii) issues invoice without supply of goods or services (fake invoice)
(iii) collects tax but fails to pay to Government within 3 months
(iv) collects tax in contravention of provisions and fails to pay
(v) fails to deduct TDS or fails to pay TDS deducted
(vi) fails to collect TCS or fails to pay TCS collected
(vii) takes or utilises ITC without actual receipt of goods or services
(viii) fraudulently obtains refund
(ix) takes or distributes ITC in contravention by ISD
(x) furnishes false information during registration or subsequently
(xi) obstructs or prevents any officer in discharge of duties
(xii) transports goods without documents
(xiii) suppresses turnover leading to tax evasion
(xiv) fails to keep, maintain or retain required records
(xv) fails to furnish information or documents required
(xvi) supplies, transports or stores goods liable to confiscation
(xvii) issues invoice using GSTIN of another person
(xviii) tampers with or destroys evidence
(xix) disposes of detained/seized/attached goods

shall be liable to pay penalty of:
- Rs. 10,000, or
- Amount of tax evaded or ITC wrongly availed,
whichever is HIGHER.

(2) Any registered person who supplies goods or services on which tax is not payable but wrongly collects and retains such tax shall be liable to penalty equal to the tax wrongly collected.

(3) Any person who aids or abets any offence shall be liable to penalty up to Rs. 25,000.

Key Points:
- Covers 19 types of offences
- Minimum penalty Rs. 10,000
- Can be equal to tax evaded
- Abetment penalty up to Rs. 25,000""",
        "summary": "Lists 19 offences with penalties of Rs. 10,000 or tax evaded (whichever higher), and Rs. 25,000 for abetment.",
        "keywords": ["penalty", "offences", "fake invoice", "tax evasion", "ITC fraud"],
        "categories": ["penalty", "offences", "enforcement"],
        "related_sections": ["Section 73", "Section 74", "Section 132"],
    },
    {
        "reference": "Section 39",
        "title": "Furnishing of Returns",
        "source_type": "gst_section",
        "content": """Section 39 of the CGST Act, 2017 - Furnishing of Returns

(1) Every registered person, other than Input Service Distributor, non-resident taxable person, person paying TDS, person paying TCS, and composition taxpayer, shall furnish a return for every tax period (GSTR-3B) on or before the twentieth day of the month succeeding such tax period.

(2) A registered person paying tax under composition scheme shall furnish a return for every quarter (CMP-08) on or before the eighteenth day of the month succeeding such quarter.

(3) Every registered person required to deduct TDS shall furnish a return (GSTR-7) within ten days after the end of the month.

(4) Every registered person required to collect TCS shall furnish a return (GSTR-8) within ten days after the end of the month.

(5) A non-resident taxable person shall furnish a return (GSTR-5) within twenty days after the end of a tax period or within seven days after the last day of registration validity, whichever is earlier.

(7) Every registered person who is required to furnish a return shall pay the tax due as per return not later than the last date for furnishing such return.

(9) If the registered person fails to furnish the return within the due date, a late fee of Rs. 100 per day for CGST and Rs. 100 per day for SGST shall be payable, subject to a maximum of Rs. 5,000.

Key Return Due Dates:
- GSTR-1: 11th of following month
- GSTR-3B: 20th of following month (varies by turnover)
- GSTR-9: 31st December of following FY

Key Points:
- Multiple return types based on taxpayer category
- Late fee: Rs. 200/day (max Rs. 5,000)
- Tax must be paid by return due date
- Non-filing can lead to registration cancellation""",
        "summary": "Mandates filing of various returns (GSTR-1, 3B, 9) with specific due dates and late fees of Rs. 200/day up to Rs. 5,000.",
        "keywords": ["returns", "GSTR-1", "GSTR-3B", "GSTR-9", "due date", "late fee"],
        "categories": ["returns", "compliance", "filing"],
        "related_sections": ["Section 37", "Section 38", "Section 44", "Section 47"],
    },
    {
        "reference": "Section 75",
        "title": "General Provisions Relating to Determination of Tax",
        "source_type": "gst_section",
        "content": """Section 75 of the CGST Act, 2017 - General Provisions Relating to Determination of Tax

(1) Where the service of notice or issuance of order is stayed by an order of court or tribunal, the period of such stay shall be excluded in computing the period specified under sections 73 and 74.

(2) Where any Appellate Authority or Tribunal or court concludes that the notice issued under section 74 is not sustainable for reason that fraud/suppression was not established, the proper officer shall determine tax under section 73.

(3) Where any order is required to be issued in pursuance of the direction of appellate authority or tribunal or court, such order shall be issued within two years from the date of communication of the said direction.

(4) An opportunity of being heard shall be granted where a request is received in writing from the person chargeable with tax or penalty, or where any adverse decision is contemplated against such person.

(5) The proper officer shall, if sufficient cause is shown by the person, adjourn the hearing and record reasons in writing.

(7) The amount of tax, interest and penalty demanded shall not exceed the amount specified in the notice and no demand shall be confirmed on any ground other than those specified in the notice.

(10) The order shall include:
(a) amount of tax, interest and penalty payable
(b) time period for payment
(c) consequences of non-payment

(12) No penalty shall be imposed for minor breaches or procedural requirements if tax has been paid and no fraud is involved. Minor breach means breach where amount is less than Rs. 5,000.

(13) The adjournment shall not be granted more than three times to a party during the proceeding.

Key Points:
- Order cannot exceed notice amount
- Personal hearing must be granted
- Maximum 3 adjournments
- Minor breaches (<Rs. 5,000) may not attract penalty
- Stay period excluded from time limits""",
        "summary": "Provides procedural safeguards including personal hearing, 3 adjournments max, order within notice amount, and minor breach exemption.",
        "keywords": ["personal hearing", "adjournment", "order", "appeal", "time limit"],
        "categories": ["procedure", "assessment", "appeal"],
        "related_sections": ["Section 73", "Section 74", "Section 107"],
    },
]

# GST Rules commonly referenced
GST_RULES = [
    {
        "reference": "Rule 36(4)",
        "title": "ITC Restriction Based on GSTR-2A/2B",
        "source_type": "gst_rule",
        "content": """Rule 36(4) of CGST Rules, 2017 - Documentary Requirements and Conditions for Claiming ITC

Input tax credit to be availed by a registered person in respect of invoices or debit notes, the details of which have not been furnished by the suppliers in GSTR-1 or using IFF, shall not exceed 5% of the eligible credit available in respect of invoices or debit notes the details of which have been furnished by the suppliers in GSTR-1 or using IFF.

Historical Changes:
- Initially 20% (Oct 2019)
- Reduced to 10% (Jan 2020)
- Reduced to 5% (Jan 2021)
- From Jan 2022: Only credit as per GSTR-2B allowed (effectively 0% extra)

Current Position (from Jan 2022):
ITC can only be claimed if it appears in GSTR-2B. No additional percentage allowed.

Practical Implications:
1. Match your ITC claims with GSTR-2B
2. Follow up with suppliers for missing invoices
3. Reconcile monthly before filing GSTR-3B
4. Excess claimed ITC may be reversed with interest

Key Points:
- ITC restricted to GSTR-2B reflected amount
- Suppliers must file GSTR-1 for recipients to claim ITC
- Mismatch can lead to notices and demand""",
        "summary": "Restricts ITC claims to amounts reflected in GSTR-2B, requiring supplier compliance with GSTR-1 filing.",
        "keywords": ["Rule 36(4)", "ITC restriction", "GSTR-2B", "GSTR-2A", "5%", "matching"],
        "categories": ["input_tax_credit", "compliance", "rules"],
        "related_sections": ["Section 16", "Section 38"],
    },
    {
        "reference": "Rule 42",
        "title": "ITC Reversal for Exempt Supplies",
        "source_type": "gst_rule",
        "content": """Rule 42 of CGST Rules, 2017 - Manner of Determination of ITC in Respect of Inputs or Input Services and Reversal Thereof

This rule applies when inputs/input services are used partly for taxable supplies and partly for exempt supplies.

Formula for ITC to be reversed:

D1 = (E ÷ F) × C

Where:
- D1 = Amount of ITC attributable to exempt supplies
- E = Value of exempt supplies during the tax period
- F = Total turnover during the tax period
- C = Common credit (ITC on inputs used for both taxable and exempt)

D2 = 5% of C (for non-business use)

Total reversal = D1 + D2

Annual Reconciliation:
At the end of financial year, recalculate based on actual figures and make adjustment in the return for September of next FY or annual return, whichever is earlier.

Key Points:
- Common credit must be apportioned
- 5% reversal for non-business use assumed
- Monthly provisional reversal required
- Annual reconciliation mandatory
- Adjustment in September return or annual return""",
        "summary": "Prescribes formula for reversing ITC on common inputs used for both taxable and exempt supplies.",
        "keywords": ["Rule 42", "ITC reversal", "exempt supplies", "apportionment", "common credit"],
        "categories": ["input_tax_credit", "reversal", "rules"],
        "related_sections": ["Section 17(2)", "Rule 43"],
    },
    {
        "reference": "Rule 86B",
        "title": "Restriction on Use of ITC for Tax Payment",
        "source_type": "gst_rule",
        "content": """Rule 86B of CGST Rules, 2017 - Restrictions on Use of Amount Available in Electronic Credit Ledger

Notwithstanding anything contained in these rules, the registered person shall not use the amount available in electronic credit ledger to discharge his liability towards output tax in excess of 99% of such tax liability, where:

The value of taxable supply (other than exempt supply and zero-rated supply) in a month exceeds Rs. 50 lakhs.

Exceptions - Rule 86B does not apply if:
(a) The registered person has paid more than Rs. 1 lakh as income tax in each of the last two financial years
(b) The registered person has received refund of more than Rs. 1 lakh under IGST in the preceding FY on account of exports
(c) The registered person has received refund of more than Rs. 1 lakh on account of inverted duty structure
(d) The registered person has discharged GST liability of more than Rs. 1 lakh other than through ITC in the preceding month

Effective From: 1st January 2021

Practical Impact:
- Minimum 1% tax must be paid in cash
- Applies only when monthly taxable turnover > Rs. 50 lakhs
- Check if any exception applies
- Maintain cash flow for GST payment

Key Points:
- 99% cap on ITC utilization for output tax
- Applies when monthly taxable turnover > Rs. 50 lakhs
- Four exceptions available
- Must pay minimum 1% in cash""",
        "summary": "Caps ITC utilization at 99% for output tax when monthly turnover exceeds Rs. 50 lakhs, requiring 1% cash payment.",
        "keywords": ["Rule 86B", "99%", "ITC restriction", "cash payment", "50 lakhs"],
        "categories": ["input_tax_credit", "compliance", "rules"],
        "related_sections": ["Section 49"],
    },
    {
        "reference": "Rule 142",
        "title": "Notice and Order for Demand of Amounts Payable",
        "source_type": "gst_rule",
        "content": """Rule 142 of CGST Rules, 2017 - Notice and Order for Demand of Amounts Payable Under the Act

(1) The proper officer shall serve notice in FORM GST DRC-01 specifying the amount of tax, interest and penalty payable.

(1A) The proper officer shall, before service of DRC-01, communicate details of any tax, interest and penalty as ascertained through FORM GST DRC-01A, providing opportunity for payment of ascertained amount.

(2) Where the person makes payment per DRC-01A, he shall inform in FORM GST DRC-03 and proceedings shall be deemed concluded.

(2A) The reply to DRC-01 shall be filed in FORM GST DRC-06 within the time specified.

(3) A summary of order in FORM GST DRC-07 shall be uploaded electronically.

(5) Where tax is payable on issuance of order, the person shall make payment within three months of order.

(6) For Section 129 (detention) and Section 130 (confiscation), payment shall be made within 7 days.

Key Forms:
- DRC-01A: Pre-notice intimation
- DRC-01: Show Cause Notice
- DRC-03: Payment acknowledgment
- DRC-06: Reply to SCN
- DRC-07: Demand Order

Key Points:
- DRC-01A issued before DRC-01 for pre-notice settlement
- DRC-06 for reply to show cause notice
- 3 months for payment after order
- 7 days for detention/confiscation cases""",
        "summary": "Prescribes procedure and forms (DRC-01, 01A, 03, 06, 07) for demand notices and orders under GST.",
        "keywords": ["Rule 142", "DRC-01", "DRC-07", "demand", "show cause notice", "order"],
        "categories": ["demand", "procedure", "rules"],
        "related_sections": ["Section 73", "Section 74", "Section 129", "Section 130"],
    },
]

# Common GST Forms
GST_FORMS = [
    {
        "reference": "Form DRC-01",
        "title": "Show Cause Notice for Demand",
        "source_type": "form_template",
        "content": """Form GST DRC-01 - Show Cause Notice under Section 73/74

Purpose: Show Cause Notice for demanding tax not paid, short paid, erroneously refunded, or ITC wrongly availed/utilized.

When Issued:
- Under Section 73: For non-fraud cases
- Under Section 74: For fraud/suppression cases

Contents:
1. Name and GSTIN of the noticee
2. Tax period involved
3. Specific charges and grounds
4. Amount of tax demanded
5. Interest calculated
6. Penalty proposed
7. Time to respond (usually 30 days)
8. Requirement to show cause

Response Required:
- File reply in Form DRC-06
- Provide documentary evidence
- Request personal hearing if needed
- Can pay tax with reduced penalty before order

Key Points:
- Must be issued before order
- States specific grounds for demand
- Gives opportunity to respond
- Penalty mentioned is maximum, can be reduced""",
        "summary": "Show Cause Notice form for tax demands under Section 73 (non-fraud) or Section 74 (fraud), requiring response via DRC-06.",
        "keywords": ["DRC-01", "show cause notice", "SCN", "demand", "Section 73", "Section 74"],
        "categories": ["forms", "demand", "compliance"],
        "related_sections": ["Section 73", "Section 74", "Rule 142"],
    },
    {
        "reference": "Form ASMT-10",
        "title": "Scrutiny Notice",
        "source_type": "form_template",
        "content": """Form GST ASMT-10 - Notice for Intimating Discrepancies in Return

Purpose: To communicate discrepancies found during scrutiny of returns.

When Issued:
- Under Section 61
- After scrutiny of GSTR-1, GSTR-3B, or other returns
- When mismatches/discrepancies are identified

Common Discrepancies Covered:
1. Mismatch between GSTR-1 and GSTR-3B
2. ITC claimed exceeding GSTR-2B
3. Turnover mismatch with e-way bills
4. Tax rate inconsistencies
5. Export without LUT claims
6. Composition to regular supplies mismatch

Response Required:
- Reply in Form ASMT-11
- Time limit: 30 days (extendable)
- Provide explanations with evidence
- Rectify returns if discrepancy accepted

Outcome:
- Accepted: No further action
- Not accepted: May lead to audit (Section 65) or demand (Section 73/74)

Key Points:
- First step in scrutiny process
- Requires detailed explanation
- Documents should support explanation
- Can request extension if needed""",
        "summary": "Scrutiny notice under Section 61 to communicate return discrepancies, requiring response via ASMT-11 within 30 days.",
        "keywords": ["ASMT-10", "scrutiny", "discrepancy", "Section 61", "mismatch"],
        "categories": ["forms", "scrutiny", "compliance"],
        "related_sections": ["Section 61", "Rule 99"],
    },
    {
        "reference": "Form REG-17",
        "title": "Show Cause Notice for Cancellation of Registration",
        "source_type": "form_template",
        "content": """Form GST REG-17 - Show Cause Notice for Cancellation of Registration

Purpose: To give notice before cancelling GST registration.

When Issued:
- Under Section 29(2)
- Non-filing of returns for 6 continuous months (regular taxpayer)
- Non-filing for 3 consecutive quarters (composition taxpayer)
- Violation of Act/Rules provisions
- Registration obtained by fraud/misrepresentation
- Business not commenced within 6 months of voluntary registration

Contents:
1. GSTIN of the taxpayer
2. Reason for proposed cancellation
3. Specific grounds and provisions violated
4. Time to respond (typically 7 working days)
5. Requirement to show cause

Response Required:
- Reply in Form REG-18
- Time limit: 7 working days
- Provide valid reasons for non-compliance
- Commit to compliance going forward
- File pending returns if that's the issue

Outcome:
- Satisfactory reply: REG-20 (cancellation dropped)
- Unsatisfactory: REG-19 (cancellation order)

Key Points:
- Personal hearing available on request
- Filing overdue returns may help case
- Cancellation can be retrospective
- ITC reversal required on cancellation""",
        "summary": "Show cause notice for registration cancellation under Section 29(2), requiring response via REG-18 within 7 working days.",
        "keywords": ["REG-17", "cancellation", "registration", "non-filing", "Section 29"],
        "categories": ["forms", "registration", "compliance"],
        "related_sections": ["Section 29", "Rule 21", "Rule 22"],
    },
]


async def generate_embedding(client: AsyncOpenAI, text: str) -> List[float]:
    """Generate embedding for text using OpenAI"""
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content"""
    return hashlib.sha256(content.encode()).hexdigest()


async def seed_entry(
    session: AsyncSession,
    client: AsyncOpenAI,
    entry: Dict[str, Any]
) -> bool:
    """Seed a single knowledge base entry with embedding"""
    try:
        reference = entry["reference"]

        # Check if entry already exists
        result = await session.execute(
            text("SELECT id FROM knowledge_base_entries WHERE reference = :ref"),
            {"ref": reference}
        )
        existing = result.fetchone()

        if existing:
            print(f"  Skipping {reference} - already exists")
            return False

        # Create knowledge base entry
        entry_id = uuid4()
        content_hash = compute_content_hash(entry["content"])

        await session.execute(
            text("""
                INSERT INTO knowledge_base_entries
                (id, source_type, reference, title, content, summary,
                 keywords, categories, related_sections, related_rules,
                 metadata, is_active, is_indexed)
                VALUES
                (:id, :source_type, :reference, :title, :content, :summary,
                 :keywords, :categories, :related_sections, :related_rules,
                 :metadata, TRUE, TRUE)
            """),
            {
                "id": str(entry_id),
                "source_type": entry["source_type"],
                "reference": reference,
                "title": entry["title"],
                "content": entry["content"],
                "summary": entry.get("summary", ""),
                "keywords": entry.get("keywords", []),
                "categories": entry.get("categories", []),
                "related_sections": entry.get("related_sections", []),
                "related_rules": entry.get("related_rules", []),
                "metadata": "{}",
            }
        )

        # Generate and store embedding
        # Combine title, summary, and content for better embedding
        embed_text = f"{entry['title']}\n\n{entry.get('summary', '')}\n\n{entry['content']}"
        embedding = await generate_embedding(client, embed_text)

        await session.execute(
            text("""
                INSERT INTO embeddings
                (id, source_type, source_id, content_hash, chunk_index,
                 content, embedding, metadata)
                VALUES
                (:id, :source_type, :source_id, :content_hash, 0,
                 :content, :embedding, :metadata)
            """),
            {
                "id": str(uuid4()),
                "source_type": entry["source_type"],
                "source_id": str(entry_id),
                "content_hash": content_hash,
                "content": entry["content"][:2000],  # Truncate for storage
                "embedding": str(embedding),
                "metadata": f'{{"reference": "{reference}", "title": "{entry["title"]}"}}',
            }
        )

        print(f"  Added {reference}")
        return True

    except Exception as e:
        print(f"  Error adding {entry['reference']}: {e}")
        return False


async def main():
    """Main seeding function"""
    print("=" * 60)
    print("GST Knowledge Base Seeder")
    print("=" * 60)

    # Initialize database
    print("\nInitializing database...")
    await init_db()

    # Initialize OpenAI client
    print("Initializing OpenAI client...")
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Get session
    session_maker = get_session_maker()

    async with session_maker() as session:
        added_count = 0

        # Seed GST Sections
        print(f"\nSeeding GST Sections ({len(GST_SECTIONS)} entries)...")
        for entry in GST_SECTIONS:
            if await seed_entry(session, client, entry):
                added_count += 1

        # Seed GST Rules
        print(f"\nSeeding GST Rules ({len(GST_RULES)} entries)...")
        for entry in GST_RULES:
            if await seed_entry(session, client, entry):
                added_count += 1

        # Seed GST Forms
        print(f"\nSeeding GST Forms ({len(GST_FORMS)} entries)...")
        for entry in GST_FORMS:
            if await seed_entry(session, client, entry):
                added_count += 1

        # Commit transaction
        await session.commit()

        print("\n" + "=" * 60)
        print(f"Seeding complete! Added {added_count} entries.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
