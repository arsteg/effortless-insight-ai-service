"""
Comprehensive GST Notice Classification Patterns

This module contains pattern definitions for 50+ GST form types
organized by category for efficient classification.
"""

from typing import Dict, List, Tuple

# Pattern format: (regex_pattern, notice_type, category, description)
NOTICE_PATTERNS: Dict[str, List[Tuple[str, str, str]]] = {
    # =========================================================================
    # DEMAND & RECOVERY NOTICES (DRC Series)
    # =========================================================================
    "demand": [
        (r'DRC[\-\s]?01[A-Z]?', "DRC-01", "Summary of Show Cause Notice"),
        (r'DRC[\-\s]?01A', "DRC-01A", "Summary of SCN for Tax Period"),
        (r'DRC[\-\s]?02', "DRC-02", "Summary of Statement"),
        (r'DRC[\-\s]?03', "DRC-03", "Intimation of Voluntary Payment"),
        (r'DRC[\-\s]?04', "DRC-04", "Acknowledgment of Voluntary Payment"),
        (r'DRC[\-\s]?05', "DRC-05", "Intimation of Conclusion of Proceedings"),
        (r'DRC[\-\s]?06', "DRC-06", "Reply to Show Cause Notice"),
        (r'DRC[\-\s]?07', "DRC-07", "Summary of Order"),
        (r'DRC[\-\s]?08', "DRC-08", "Rectification of Order"),
        (r'DRC[\-\s]?09', "DRC-09", "Order for Recovery by Deduction"),
        (r'DRC[\-\s]?10', "DRC-10", "Notice for Recovery by Sale"),
        (r'DRC[\-\s]?11', "DRC-11", "Attachment of Debt/Property"),
        (r'DRC[\-\s]?12', "DRC-12", "Notice to Third Party"),
        (r'DRC[\-\s]?13', "DRC-13", "Notice for Recovery"),
        (r'DRC[\-\s]?14', "DRC-14", "Certificate of Recovery"),
        (r'DRC[\-\s]?15', "DRC-15", "Application for Withdrawal"),
        (r'DRC[\-\s]?16', "DRC-16", "Appeal Against Penalty Order"),
        (r'DRC[\-\s]?17', "DRC-17", "Order of Detention/Seizure"),
        (r'DRC[\-\s]?18', "DRC-18", "Bond for Provisional Release"),
        (r'DRC[\-\s]?19', "DRC-19", "Order of Confiscation"),
        (r'DRC[\-\s]?20', "DRC-20", "Application for Deferred Payment"),
        (r'DRC[\-\s]?21', "DRC-21", "Order on Application for Deferment"),
        (r'DRC[\-\s]?22', "DRC-22", "Provisional Attachment Order"),
        (r'DRC[\-\s]?23', "DRC-23", "Restoration of Attached Property"),
        (r'DRC[\-\s]?24', "DRC-24", "Order of Auction"),
        (r'DRC[\-\s]?25', "DRC-25", "Certificate of Sale"),
    ],

    # =========================================================================
    # ASSESSMENT NOTICES (ASMT Series)
    # =========================================================================
    "assessment": [
        (r'ASMT[\-\s]?01', "ASMT-01", "Application for Provisional Assessment"),
        (r'ASMT[\-\s]?02', "ASMT-02", "Provisional Assessment Order"),
        (r'ASMT[\-\s]?03', "ASMT-03", "Application for Final Assessment"),
        (r'ASMT[\-\s]?04', "ASMT-04", "Final Assessment Order"),
        (r'ASMT[\-\s]?05', "ASMT-05", "Bond for Provisional Assessment"),
        (r'ASMT[\-\s]?06', "ASMT-06", "Notice for Scrutiny"),
        (r'ASMT[\-\s]?07', "ASMT-07", "Bank Guarantee for Provisional Assessment"),
        (r'ASMT[\-\s]?08', "ASMT-08", "Application for Extension of Bond"),
        (r'ASMT[\-\s]?09', "ASMT-09", "Order for Extension of Bond"),
        (r'ASMT[\-\s]?10', "ASMT-10", "Show Cause Notice for Assessment"),
        (r'ASMT[\-\s]?11', "ASMT-11", "Reply to ASMT-10"),
        (r'ASMT[\-\s]?12', "ASMT-12", "Assessment Order"),
        (r'ASMT[\-\s]?13', "ASMT-13", "Best Judgment Assessment Notice"),
        (r'ASMT[\-\s]?14', "ASMT-14", "Ad-hoc/Addendum Assessment Notice"),
        (r'ASMT[\-\s]?15', "ASMT-15", "Order under Section 63"),
        (r'ASMT[\-\s]?16', "ASMT-16", "Assessment under Section 64"),
        (r'ASMT[\-\s]?17', "ASMT-17", "Withdrawal of Assessment"),
        (r'ASMT[\-\s]?18', "ASMT-18", "Audit Findings Intimation"),
    ],

    # =========================================================================
    # REGISTRATION NOTICES (REG Series)
    # =========================================================================
    "registration": [
        (r'REG[\-\s]?01', "REG-01", "Application for Registration"),
        (r'REG[\-\s]?02', "REG-02", "Acknowledgement of Registration Application"),
        (r'REG[\-\s]?03', "REG-03", "Notice for Seeking Clarification"),
        (r'REG[\-\s]?04', "REG-04", "Reply to Clarification Notice"),
        (r'REG[\-\s]?05', "REG-05", "Order of Rejection"),
        (r'REG[\-\s]?06', "REG-06", "Registration Certificate"),
        (r'REG[\-\s]?07', "REG-07", "Application for Amendment"),
        (r'REG[\-\s]?08', "REG-08", "Order of Amendment"),
        (r'REG[\-\s]?09', "REG-09", "Application for Core Field Amendment"),
        (r'REG[\-\s]?10', "REG-10", "Temporary Registration Number"),
        (r'REG[\-\s]?11', "REG-11", "Extension of Registration Period"),
        (r'REG[\-\s]?12', "REG-12", "Grant of UIN"),
        (r'REG[\-\s]?13', "REG-13", "Application for TDS/TCS Registration"),
        (r'REG[\-\s]?14', "REG-14", "Application for Amendment (TDS/TCS)"),
        (r'REG[\-\s]?15', "REG-15", "Application for Amendment under Section 28"),
        (r'REG[\-\s]?16', "REG-16", "Application for Voluntary Cancellation"),
        (r'REG[\-\s]?17', "REG-17", "Show Cause Notice for Cancellation"),
        (r'REG[\-\s]?18', "REG-18", "Reply to Cancellation Notice"),
        (r'REG[\-\s]?19', "REG-19", "Order of Cancellation"),
        (r'REG[\-\s]?20', "REG-20", "Order of Dropping Proceedings"),
        (r'REG[\-\s]?21', "REG-21", "Application for Revocation"),
        (r'REG[\-\s]?22', "REG-22", "Order of Revocation"),
        (r'REG[\-\s]?23', "REG-23", "Show Cause for Suspension"),
        (r'REG[\-\s]?24', "REG-24", "Order of Suspension"),
        (r'REG[\-\s]?25', "REG-25", "Certificate after Physical Verification"),
        (r'REG[\-\s]?26', "REG-26", "Application for Enrolment (GST Practitioner)"),
        (r'REG[\-\s]?27', "REG-27", "Show Cause Notice (GST Practitioner)"),
        (r'REG[\-\s]?28', "REG-28", "Order of Cancellation (GST Practitioner)"),
        (r'REG[\-\s]?29', "REG-29", "Application for Field Visit"),
        (r'REG[\-\s]?30', "REG-30", "Field Visit Report"),
        (r'REG[\-\s]?31', "REG-31", "Migration Application"),
    ],

    # =========================================================================
    # AUDIT NOTICES (ADT Series)
    # =========================================================================
    "audit": [
        (r'ADT[\-\s]?01', "ADT-01", "Audit Intimation Notice"),
        (r'ADT[\-\s]?02', "ADT-02", "Audit Report"),
        (r'ADT[\-\s]?03', "ADT-03", "Communication of Audit Findings"),
        (r'ADT[\-\s]?04', "ADT-04", "Final Audit Report"),
    ],

    # =========================================================================
    # RETURNS & COMPLIANCE (GSTR/RET Series)
    # =========================================================================
    "returns": [
        (r'GSTR[\-\s]?1', "GSTR-1", "Outward Supplies Return"),
        (r'GSTR[\-\s]?2A', "GSTR-2A", "Auto-drafted Input Tax Credit"),
        (r'GSTR[\-\s]?2B', "GSTR-2B", "Auto-drafted ITC Statement"),
        (r'GSTR[\-\s]?3A', "GSTR-3A", "Notice for Non-filing of Returns"),
        (r'GSTR[\-\s]?3B', "GSTR-3B", "Summary Return"),
        (r'GSTR[\-\s]?4', "GSTR-4", "Composition Scheme Return"),
        (r'GSTR[\-\s]?5', "GSTR-5", "Non-Resident Return"),
        (r'GSTR[\-\s]?6', "GSTR-6", "Input Service Distributor Return"),
        (r'GSTR[\-\s]?7', "GSTR-7", "TDS Return"),
        (r'GSTR[\-\s]?8', "GSTR-8", "E-commerce TCS Return"),
        (r'GSTR[\-\s]?9', "GSTR-9", "Annual Return"),
        (r'GSTR[\-\s]?9A', "GSTR-9A", "Composition Annual Return"),
        (r'GSTR[\-\s]?9C', "GSTR-9C", "Reconciliation Statement"),
        (r'GSTR[\-\s]?10', "GSTR-10", "Final Return"),
        (r'GSTR[\-\s]?11', "GSTR-11", "UIN Holder Return"),
        (r'RET[\-\s]?01', "RET-01", "Return Non-filing Notice"),
        (r'RET[\-\s]?02', "RET-02", "Notice for Difference in Liability"),
        (r'RET[\-\s]?03', "RET-03", "ITC Mismatch Notice"),
    ],

    # =========================================================================
    # REFUND NOTICES (RFD Series)
    # =========================================================================
    "refund": [
        (r'RFD[\-\s]?01', "RFD-01", "Refund Application"),
        (r'RFD[\-\s]?02', "RFD-02", "Acknowledgement of Refund Application"),
        (r'RFD[\-\s]?03', "RFD-03", "Deficiency Memo"),
        (r'RFD[\-\s]?04', "RFD-04", "Provisional Refund Order"),
        (r'RFD[\-\s]?05', "RFD-05", "Refund Sanction Order"),
        (r'RFD[\-\s]?06', "RFD-06", "Final Refund Order"),
        (r'RFD[\-\s]?07', "RFD-07", "Order Withholding Refund"),
        (r'RFD[\-\s]?08', "RFD-08", "Show Cause Notice for Refund Rejection"),
        (r'RFD[\-\s]?09', "RFD-09", "Reply to Refund SCN"),
        (r'RFD[\-\s]?10', "RFD-10", "Refund Application (SEZ)"),
        (r'RFD[\-\s]?11', "RFD-11", "Endorsement by SEZ Officer"),
    ],

    # =========================================================================
    # APPEAL NOTICES (APL Series)
    # =========================================================================
    "appeal": [
        (r'APL[\-\s]?01', "APL-01", "Appeal to Appellate Authority"),
        (r'APL[\-\s]?02', "APL-02", "Acknowledgement of Appeal"),
        (r'APL[\-\s]?03', "APL-03", "Appeal to Appellate Tribunal"),
        (r'APL[\-\s]?04', "APL-04", "Appeal Order"),
        (r'APL[\-\s]?05', "APL-05", "Summary of Demands"),
        (r'APL[\-\s]?06', "APL-06", "Cross Objection"),
        (r'APL[\-\s]?07', "APL-07", "Appeal Fee Payment"),
        (r'APL[\-\s]?08', "APL-08", "Stay Application"),
    ],

    # =========================================================================
    # INSPECTION & SEIZURE (INS Series)
    # =========================================================================
    "inspection": [
        (r'INS[\-\s]?01', "INS-01", "Authorization for Inspection"),
        (r'INS[\-\s]?02', "INS-02", "Order for Search and Seizure"),
        (r'INS[\-\s]?03', "INS-03", "Order for Provisional Release"),
        (r'INS[\-\s]?04', "INS-04", "Bond for Provisional Release"),
        (r'INS[\-\s]?05', "INS-05", "Order of Confiscation"),
    ],

    # =========================================================================
    # E-WAY BILL NOTICES (EWB Series)
    # =========================================================================
    "eway_bill": [
        (r'EWB[\-\s]?01', "EWB-01", "E-Way Bill Generation"),
        (r'EWB[\-\s]?02', "EWB-02", "E-Way Bill Cancellation"),
        (r'EWB[\-\s]?03', "EWB-03", "Detention Notice"),
        (r'EWB[\-\s]?04', "EWB-04", "Vehicle Interception Notice"),
        (r'MOV[\-\s]?01', "MOV-01", "Detention Order for Goods"),
        (r'MOV[\-\s]?02', "MOV-02", "Physical Verification Report"),
        (r'MOV[\-\s]?03', "MOV-03", "Seizure Order"),
        (r'MOV[\-\s]?04', "MOV-04", "Bond for Release"),
        (r'MOV[\-\s]?05', "MOV-05", "Release Order"),
        (r'MOV[\-\s]?06', "MOV-06", "Show Cause Notice"),
        (r'MOV[\-\s]?07', "MOV-07", "Reply to MOV-06"),
        (r'MOV[\-\s]?08', "MOV-08", "Order under Section 129"),
        (r'MOV[\-\s]?09', "MOV-09", "Order of Confiscation"),
        (r'MOV[\-\s]?10', "MOV-10", "Notice for Penalty"),
        (r'MOV[\-\s]?11', "MOV-11", "Confiscation Order"),
    ],

    # =========================================================================
    # ITC RELATED NOTICES (ITC Series)
    # =========================================================================
    "itc": [
        (r'ITC[\-\s]?01', "ITC-01", "Declaration for ITC Transitional"),
        (r'ITC[\-\s]?02', "ITC-02", "Declaration for Stock Transfer"),
        (r'ITC[\-\s]?03', "ITC-03", "ITC Reversal Declaration"),
        (r'ITC[\-\s]?04', "ITC-04", "Job Work Declaration"),
        (r'PMT[\-\s]?01', "PMT-01", "Electronic Cash Ledger"),
        (r'PMT[\-\s]?02', "PMT-02", "Electronic Credit Ledger"),
        (r'PMT[\-\s]?03', "PMT-03", "Refund from Electronic Cash Ledger"),
        (r'PMT[\-\s]?04', "PMT-04", "Reversal of Erroneous Refund"),
        (r'PMT[\-\s]?05', "PMT-05", "Intimation for Mismatch"),
        (r'PMT[\-\s]?06', "PMT-06", "Order for Deposit of Tax"),
        (r'PMT[\-\s]?07', "PMT-07", "Application for Refund of ITC"),
        (r'PMT[\-\s]?09', "PMT-09", "Transfer of Cash Ledger Balance"),
    ],

    # =========================================================================
    # COMPOSITION SCHEME (CMP Series)
    # =========================================================================
    "composition": [
        (r'CMP[\-\s]?01', "CMP-01", "Intimation of Composition Levy"),
        (r'CMP[\-\s]?02', "CMP-02", "Acknowledgement of Intimation"),
        (r'CMP[\-\s]?03', "CMP-03", "Intimation of Details of Stock"),
        (r'CMP[\-\s]?04', "CMP-04", "Intimation to Opt Out"),
        (r'CMP[\-\s]?05', "CMP-05", "Notice for Denial/Withdrawal"),
        (r'CMP[\-\s]?06', "CMP-06", "Reply to CMP-05"),
        (r'CMP[\-\s]?07', "CMP-07", "Order for Withdrawal"),
        (r'CMP[\-\s]?08', "CMP-08", "Statement cum Challan"),
    ],
}

# Flat list of all patterns for quick matching
ALL_PATTERNS: List[Tuple[str, str, str, str]] = []
for category, patterns in NOTICE_PATTERNS.items():
    for pattern, notice_type, description in patterns:
        ALL_PATTERNS.append((pattern, notice_type, category, description))

# Notice type to category mapping
TYPE_TO_CATEGORY: Dict[str, str] = {
    notice_type: category
    for category, patterns in NOTICE_PATTERNS.items()
    for _, notice_type, _ in patterns
}

# Total count of supported notice types
TOTAL_NOTICE_TYPES = len(ALL_PATTERNS)
