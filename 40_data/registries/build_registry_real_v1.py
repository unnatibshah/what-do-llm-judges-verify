"""Build registry_real.json from the blind text corpus. Snippets are sliced from the text files so they are verbatim."""
import json
import datetime
import pathlib

BASE = pathlib.Path(__file__).parent
TXT = {p.stem: p.read_text(encoding="utf-8") for p in (BASE / "text").glob("*.txt")}
DOCS = {d["doc_id"]: d for d in json.loads((BASE / "documents.json").read_text(encoding="utf-8"))}


FAILS = []


def cut(doc, start, end, anchor=None):
    t = TXT[doc]
    a = t.index(anchor) if anchor else 0
    try:
        i = t.index(start, a)
    except ValueError:
        FAILS.append(f"START {doc}: {start!r}"); return "<<FAIL>>"
    try:
        j = t.index(end, i) + len(end)
    except ValueError:
        FAILS.append(f"END {doc}: {end!r} (start {start[:40]!r})"); return "<<FAIL>>"
    s = t[i:j]
    return s[:600]


def eff(doc):
    e = DOCS[doc]["effective_date"]
    return None if e in (None, "UNKNOWN") else e


JUR = lambda doc: doc[:2]
nodes, edges = [], []
IDX = {}


def node(doc, ref, topic, start, end, anchor=None, date="doc", conf="high", note=None):
    nid = f"{doc}#cl-{ref}"
    n = {"node_id": nid, "doc_id": doc, "jurisdiction": JUR(doc), "clause_ref": ref, "topic": topic,
         "snippet": cut(doc, start, end, anchor), "effective_date": eff(doc) if date == "doc" else date,
         "confidence": conf}
    if note:
        n["note"] = note
    assert nid not in IDX, nid
    IDX[nid] = n
    nodes.append(n)


def edge(frm, to, typ, quote_doc, qstart, qend, conf, anchor=None, reason=None):
    assert frm in IDX and to in IDX, (frm, to)
    e = {"from_node": frm, "to_node": to, "type": typ, "effective_date": IDX[to]["effective_date"],
         "evidence_quote": cut(quote_doc, qstart, qend, anchor), "confidence": conf}
    if reason:
        e["reason"] = reason
    edges.append(e)


# ---------------- MAHARASHTRA: MERC GIRREGS 2019 (principal) ----------------
D = "MH-C3-001"
node(D, "2.1(j)", "eligibility; capacity limit (1 MW net metering)", "(j) “Eligible Consumer” means", "shall not apply;")
node(D, "5.2", "distribution transformer hosting limit (70%)", "5.2 The cumulative capacity of all Renewable", "rated capacity:")
node(D, "6.1", "minimum system size (1 kW)", "6.1 The minimum size", "would be 1 kW.")
node(D, "6.2", "capacity limit vs sanctioned load/contract demand", "6.2 The capacity of the Renewable", "Consumer, as applicable.")
node(D, "6.3", "capacity subject to DT cumulative capacity", "6.3 The maximum Renewable Energy Generating System capacity", "range of five percent\nshall be allowed.")
node(D, "6.6", "eligibility: consumers with arrears excluded", "6.6 Consumers with pending arrears", "under these Regulations.")
node(D, "8.3", "metering: net meter at interconnection", "8.3 The Net Metering Arrangement shall include", "Distribution Licensee.")
node(D, "8.10", "metering threshold: check meter above 20 kW", "8.10 In case of Renewable Energy Generating System with capacity above 20 kW", "up to and including 20 kW.")
node(D, "8.11", "metering: check meter under net billing", "8.11 In case of Renewable Energy Generating System set up under Net Billing", "installed by the Distribution Licensee.")
node(D, "9.5", "application procedure/timelines (Annexure 1)", "9.5 The procedure for application for connectivity", "Regulations.")
node(D, "9.7", "rejection notice / DT capacity constraint", "9.7 Before rejecting any application", "constraint is\nrectified.")
node(D, "9.8", "approval validity (6 months)", "9.8 The approval for connectivity", "agreed to by the Distribution Licensee:")
node(D, "11.4(d)", "net metering ToD settlement", "d) In case the Eligible Consumer is within the ambit of Time of Day", "off-\npeak hours;")
node(D, "11.5", "grid support charges; exemption up to 10 kW", "Provided that the consumers of all Categories having Sanctioned Load up to 10 kW", "for Net Metering systems:")
node(D, "12.1", "net billing arrangement definition/scope", "12.1 Net billing is the arrangement", "Power Purchase\nAgreement:")
node(D, "Annexure-1.c", "technical feasibility study timeline (15 working days)", "c. The Distribution Licensee shall conduct a technical feasibility study", "relevant Distribution Transformer.")
node(D, "Annexure-1.e", "approval timeline (7 working days) and validity", "e. If found technically feasible", "agreed to by the Distribution Licensee.")
node(D, "Annexure-1.g", "commissioning timeline (10+10 working days)", "g. The Distribution Licensee shall complete the testing and commissioning", "days thereafter.")
node(D, "Annexure-1.h", "connection agreement before synchronisation", "h. The Eligible Consumer and Distribution Licensee shall enter", "synchronized with the distribution network.")
node(D, "20", "repeal and savings (MERC Net Metering Regs 2015)", "20 Repeal and Savings", "signed under the aforesaid Regulations.")

# ---------------- MH First Amendment 2023 (English half, page 13+) ----------------
D, A = "MH-C3-003", "--- Page 13 ---"
node(D, "2.1(j)", "eligibility; capacity limit (5 MW or CD/SL net metering)", "Provided further that in case of Net Metering Arrangement, the capacity", "Contract Demand/Sanctioned Load of consumer.”", A)
node(D, "8.3", "metering: net meter (net metering or net billing)", "“8.3 The Net Metering Arrangement or Net Billing", "ascertained by the Distribution Licensee.”", A)
node(D, "8.11", "metering: check meter under gross metering", "“8.11 In case of Renewable Energy Generating System set up under Gross Metering", "installed by the Distribution Licensee.”", A)
node(D, "9.5", "application timelines; Rs 500/day delay compensation", "“ 9.5 The procedure for application for connectivity", "delay in performing the activity.”", A)
node(D, "11.5", "grid support charges not levied till 5000 MW (2nd proviso)", "“Provided further that the Grid Support Charges shall not be levied", "the same shall\ncontinue.”", A)
node(D, "12.1", "gross metering arrangement (substituted Reg 12/12.1)", "“12. Gross Metering – Energy Accounting and Settlement", "with a Net Meter.”", A)
node(D, "Annexure-1.h", "connection agreement (incl. gross metering) before synchronisation", "“(h) The Eligible Consumer and Distribution Licensee shall enter", "synchronized with the distribution\nnetwork.”", A)

# ---------------- MH Second Amendment 2024 (official English, page 6+) ----------------
D, A = "MH-C3-002", "--- Page 6 ---"
node(D, "2.1(j)", "eligibility: virtual net metering provisos (4th/5th)", "“Provided also that Residential consumer in multi storied building can setup Renewable", "eligible to each\nparticipating consumer.”", A)
node(D, "8.11", "metering: check meter under gross and virtual net metering", "“8.11 In case of Renewable Energy Generating System set up under Gross Metering\nArrangement and Virtual", "Licensee.”", A)
node(D, "9.7", "rejection notice (15 days); seniority", "“9.7 Before rejecting any application", "chronological order of seniority.”", A)
node(D, "9.7(a)", "DT/service-line upgradation by licensee; cost in ARR", "“ 9.7 (a) During the time period from the feasibility study", "annual revenue requirement of the Distribution Licensee.”", A)
node(D, "Annexure-1.c", "feasibility study 15 days, presumed feasible; deemed approval up to 10 kW", "“ c For installation of Renewable Energy Generating Systems", "carried out by the Distribution Licensee.”", A)

# ---------------- MERC Order Case 217 of 2024 (MSEDCL MYT tariff order) ----------------
D = "MH-C3-004"
node(D, "7.13.79", "net metering ToD banking for LT-residential RTS", "7.13.79 Hence, the Commission further rules", "slot wise banking requirement.", conf="medium")
node(D, "7.1.34", "grid support charges not approved (below 5000 MW)", "7.1.34 Based on MSEDCL’s own submission", "akin to Tariff proceeding.", conf="medium")

# ---------------- MSEDCL circulars ----------------
D = "MH-C5-001"
node(D, "2.1", "eligibility (restates 2019 Reg 2.1(j), <1 MW)", "2.1\"Eligible Consumer\" means", "the capacity limit of 1\nMW shall not apply\"", conf="medium")
node(D, "5.2", "capacity limit vs sanctioned load/contract demand", "5.2 The capacity of the Renewable Energy Generating System to be connected", "Consumer, as applicable.", conf="medium")
node(D, "5.3", "DT hosting limit 70%", "5.3 The maximum Renewable Energy Generating System capacity", "five percent shall be allowed.", conf="medium")
node(D, "5.6", "eligibility: arrears excluded", "5.6 Consumers with pending arrears with the MSEDCL", "under these Regulations.", conf="medium")
node(D, "8.9", "metering threshold: check meter above 20 kW", "8.9 Check Meter of appropriate class", "capacity above 20 kW.", conf="medium")
node(D, "9.8", "approval validity 6 months", "9.8 The approval for connectivity from the MSEDCL", "apply afresh.", conf="medium")

D = "MH-C5-005"
node(D, "2", "CFA eligibility (Phase-II, residential/GHS only)", "The program provides for Central Financial Assistance (CFA) for the household", "Regulations 20j.9.", conf="medium")
node(D, "3.2", "CFA slab Phase-II (40% up to 3 kWp, 20% 3-10 kWp)", "3 3 . . 1 2 C C F F A A", "the CFA would be limited lo20%", conf="low",
     note="OCR of 3.1/3.2 is garbled (interleaved characters); slab reading corroborated by illustration at 3.15")
node(D, "3.3", "CFA slab Phase-II GHS/RWA 20%", "3.3 CFA@20%forGHS/RWAcapacityupto500Kwp", "and total uPto 500 kwP)'", conf="medium")
node(D, "3.7", "DCR: indigenous cells and modules for CFA", "3.7 oNLYlNDlGENoUSLYmanufacturedsolarmoduleswithlNDlGENoUSLY", "eligible for cFA'", conf="medium")

D = "MH-C5-006"
node(D, "3", "arrears no bar to processing (PMSG)", "3. In cases, where RTS application received with pending arrears", "New Connection System.", conf="medium")
node(D, "4", "deemed/auto feasibility up to 10 kW; auto load enhancement", "4. In cases where applied PV capacity is higher than Sanction load", "New Connection\nSystem.", conf="medium")
node(D, "5", "feasibility above 10 kW auto-approved after 15 days", "5. The technical feasibility of RTS PV capacity above 10 KW", "within 15 days.", conf="medium")

D = "MH-C6-001"
node(D, "GCR-2", "CFA slab (MEDA FAQ, Phase-II era)", "2. How much is the subsidy?", "20% subsidy of benchmark cost.", conf="low",
     note="Undated FAQ, machine-translated from Marathi; FAQ numbering under 'Grid Connected Rooftop' heading")

# ---------------- RAJASTHAN ----------------
D = "RJ-C3-001"
note15 = "Source is an RERC summary table of the 2015 Regulations 'with amendment Dated: March, 2019'; clause_ref is the table Sl. No., not the regulation number"
node(D, "2", "DT hosting limit 30%", "The cumulative capacity to be allowed at a particular distribution transformer shall not exceed 30%", "as well as to the Commission.", conf="medium", note=note15)
node(D, "3", "capacity limit 80% of sanctioned load; 1 kWp-1 MWp", "1. The maximum Rooftop PV Solar Power Plant capacity", "1 MWp (1000 kWp). |", conf="medium", note=note15)
node(D, "6", "net metering settlement (Rs 3.14/unit)", "2. The electricity injected by a domestic category consumer", "shall be applicable.", conf="medium", note=note15)
node(D, "10", "metering threshold: check meter above 250 kW", "Check meters shall be mandatory for rooftop solar systems having capacity more than 250 kW.", "solar check meters would be optional.", conf="medium", note=note15)

D = "RJ-C3-002"
node(D, "1.4", "coexistence with 2015 Regulations; grandfathering", "1.4 These Regulations shall remain in force along with", "subsequent amendments\nthereof.")
node(D, "3.2", "eligibility for net metering per ROC Rules 2020", "3.2 These Regulations shall apply to:", "cannot be changed.")
node(D, "3.4", "applicability: systems commissioned on/after 1 July 2021", "3.4 These Regulations shall be applicable to all Grid interactive", "amendments thereof:")
node(D, "4.2", "eligibility: arrears excluded", "4.2 Consumers having pending arrears", "Section\n56 of the Act.")
node(D, "6.1", "DT hosting limit 50%", "6.1 The cumulative capacity of Renewable Energy generating system to be allowed", "Regulation 7.2 of these Regulations.")
node(D, "7.2", "capacity limit 100% of sanctioned load/contract demand", "7.2 The maximum Renewable Energy generating system capacity to be installed at any", "amendments thereto.")
node(D, "7.3", "capacity >1 kW and up to 1 MW", "7.3 The capacity of Renewable Energy generating system to be installed at the premises", "subsequent amendments thereof.")
node(D, "8.8", "technical feasibility within 20 days", "8.8 Within twenty (20) days", "Renewable Energy generating system.")
node(D, "8.9", "letter of approval within 30 days", "8.9 If technical feasibility is found satisfactory", "acknowledgement of the application.")
node(D, "8.12", "commissioning within 30 days of installation certificate", "8.12 After installation of Renewable Energy generating system", "web-portal of the Distribution Licensee.")
node(D, "10.14.3", "behind-the-meter energy cap (CUF+5%)", "10.14.3 The maximum permissible energy that can be consumed", "plus 5 percent.")
node(D, "11.10", "metering: consumer-installed check meter", "11.10 A consumer, at his own cost, shall also install a Check Meter", "defective/failure/burnt\ncondition.")
node(D, "12.5.2", "net billing tariff (bid tariff +25%)", "12.5.2 The Distribution Licensee shall enter into Connection Agreement", "entire duration of the\nAgreement.")
node(D, "12.5.6", "net billing energy cap (CUF+5%)", "12.5.6 The maximum permissible energy that can be generated", "plus 5 percent.")
node(D, "12.6.1(a)", "net metering surplus purchase (domestic)", "a) If the quantum of electricity exported by a domestic category consumer", "immediately succeeding billing cycle:")
node(D, "12.6.1(b)", "net metering billing at highest slab (first proviso)", "Provided that, for Net Metered consumers the Net imported energy", "total consumption from all\nsources.")
node(D, "12.6.1(d)", "net metering energy cap (CUF+5%)", "d) The maximum permissible energy that can be consumed from Renewable Energy\ngenerating system installed under the Net Metering", "plus 5 percent.")
node(D, "15.2", "charges exemption for RESCO net metering", "15.2 The quantum of electricity generated from the RESCO-owned", "additional surcharge applicable for open access consumers.")

D, A = "RJ-C3-003", "--- Page 5 ---"
node(D, "6.1", "DT hosting limit 80%; augmentation at licensee cost", "\"6.1 The cumulative capacity of Renewable Energy generating system to be allowed", "Regulations.\"", A)
node(D, "10.14.3", "behind-the-meter peak AC capacity cap", "\"The peak AC capacity (inverter capacity on AC side) of the Renewable Energy\ngenerating station installed behind", "deemed drawl from the Discom.\"", A)
node(D, "12.5.2", "net billing tariff (bid tariff +40%)", "\"12.5.2 The Distribution Licensee shall enter into Connection Agreement", "plus an incentive of 40% shall be applicable:\"", A)
node(D, "12.5.6", "net billing peak AC capacity cap", "“12.5.6 The peak AC capacity", "shall\nlapse.", A)
node(D, "12.6.1(a)", "net metering surplus purchase (+25%)", "“a) If the quantum of electricity exported by a domestic category consumer", "payable in the immediately succeeding billing cycle:”", A)
node(D, "12.6.1(b)", "net metering billing at applicable slab (first proviso)", "“Provided that, for Net Metering consumers the Net imported energy", "from all sources.”", A)
node(D, "12.6.1(d)", "net metering peak AC capacity cap", "“d) The peak AC capacity", "AC capacity the corresponding excess", A)
node(D, "15.2", "no CSS/AS for RESCO net metering for domestic/govt (3rd proviso)", "“Provided also that no cross-subsidy surcharge", "public undertakings of the State Govt.”", A)

D = "RJ-C3-004"
node(D, "12", "net metering allowed up to 1 MW or sanctioned load/CD", "12. In view of above, the Commission under its power", "for all\ncategories of the consumers.")

D, A = "RJ-C3-005", "RAJASTHAN STATE ELECTRICITY REGULATORY COMMISSION"
node(D, "8.8", "feasibility 15 days, presumed feasible; deemed approval up to 10 kW", "“For installation of Renewable Energy Generating systems, the technical feasibility", "Distribution Licensee.”", A)
node(D, "8.12", "commissioning within 15 days of installation certificate", "“After installation of Renewable Energy Generating system, the consumer shall", "Distribution Licensee.”", A)
node(D, "12.6.1(a)", "educational institutions may opt net billing two months (3rd proviso)", "“Provided also that suchEducational Institutions", "commencement of such period.”", A)

D = "RJ-C5-002"
node(D, "4.1", "JVVNL procedure: DT hosting limit 80%", "'Thc cumulativc capacity of Rencwable Encrgy", "order No.JPR5-1073.", conf="medium",
     note="Amends clause 4.1 of JVVNL order JPR5-1073 (21.09.2021), which is not in the corpus")

D = "RJ-C5-001"
node(D, "p3", "solar application doubles as load extension (capacity > sanctioned load)", "If the applied SPV plant capacity is more than the sanctioned load", "No separate file will be", conf="medium",
     note="Unnumbered paragraph (third operative paragraph) of the JVVNL SOP")

# ---------------- CENTRAL (IN) ----------------
D = "IN-C3-002"
node(D, "11(2)", "RE capacity limit as specified by Commission", "(2) Renewable Energy (RE) generation unit may also be set up", "limit as specified by the Commission.")
node(D, "11(4)", "metering threshold: net metering up to 10 kW, gross above", "(4) The regulations on Grid Interactive Roof top Solar PV system", "gross metering for loads above ten kW.")
node(D, "11(7)", "technical feasibility within 20 days", "(7) The technical feasibility study shall be completed within the time period specified by the", "intimated to the\napplicant.")
node(D, "11(8)", "infrastructure upgradation by licensee or consumer", "(8) During the time period from the feasibility study till the completion", "as the case may\nbe.")
node(D, "11(9)", "commissioning within 30 days of installation certificate", "(9) After installation of solar PV system, the consumer shall submit", "on web-portal of the distribution licensee.")

D, A = "IN-C3-001", "MINISTRY OF POWER"
node(D, "11(7)", "technical feasibility 15 days, presumed feasible", "“(7) For installation of roof top solar photo voltaic systems", "presumed that the proposal is technically feasible.", A)
node(D, "11(7A)", "deemed approval up to 10 kW; load enhancement by licensee", "(7A) The applications for roof top solar photo voltaic systems upto 10 kW", "carried out by the distribution licensee.”", A)
node(D, "11(8)", "infrastructure upgradation; cost in ARR up to 5 kW", "Provided that the cost of strengthening the distribution infrastructure", "revenue requirement of the distribution\nlicensee.", A)
node(D, "11(9)", "commissioning within 15 days of installation certificate", "“(9) After installation of roof top solar photovoltaic system", "submission of the installation certificate.", A)

D = "IN-C1-002"
node(D, "2", "CFA slab Phase-II (40% up to 3 kW, 20% 3-10 kW)", "2, Accordingly, it is clarified that subsidy", "subsidy beyond 10 kW capacity.", conf="medium")

D = "IN-C1-009"
node(D, "2.iii", "technical feasibility within 15 working days (national portal)", "Theapplicationwillbeforwardedonlinetotheconcerned DISCOMforissuanceof", "workingdays.", conf="medium")
node(D, "2.iv", "DCR and ALMM modules required", "After obtainingtechnical feasibility, thebeneficiarywill install", "certifiedby BIS.", conf="medium")

D = "IN-C1-003"
node(D, "1", "Phase-II deemed subsumed in PMSG from 13.02.2024", "The sanction of the President of India is hereby granted", "i.e.,13.02.2024.", date="2024-02-13", conf="medium")
node(D, "3", "CFA slab PMSG (60% first 2 kW, 40% next 1 kW; Rs 30,000/18,000)", "Thesubsidy/CFAunder the PM-Surya Ghar", "costofadditionalk W", date="2024-02-13", conf="medium")

D = "IN-C1-001"
A = "--- Page 3 ---"
node(D, "4(a)", "Phase-II scheme subsumed", "Rooftop Solar Phase II Programme since 2019", "Muft Bijli Yojana.", A, conf="medium")
node(D, "5(b)", "CFA eligibility: residential RTS incl. GNM/VNM", "b) Eligibility: For the purpose of CFA", "approved by the DISCOM.", A)
node(D, "5(d)", "no CFA to non-residential", "d) No CFA will be provided to non-residential", "industrial segment etc.).", A)
node(D, "5(e)", "CFA slab PMSG (60%/40%/none beyond 3 kWp; GHS/RWA)", "e) CFA Structure: The Central Financial Assistance", "As per CFA of S. No. (2) above |", A)
node(D, "5(f)", "GHS/RWA connection for common facilities only", "f) The GHS/RWA connection eligible under the scheme", "Cooperative Housing Societies etc.", A)
node(D, "5(h)", "effective CFA Rs 30,000/18,000 per kWp", "h) Effective CFA: The CFA for the scheme", "| Rs 18,000/kWp | Rs 19,800/kWp |\n\nTo illustrate", A)
node(D, "5(i)", "additional state subsidy", "i) Additional State Subsidy: The State/UT governments may supplement", "integrated with the National Portal.", A)
node(D, "5(m)", "DCR mandate for CFA", "m) Domestic Content Requirement: Solar modules used", "ineligible for CFA.", A)
node(D, "5(n)", "pre-existing RTS: CFA for balance capacity up to 3 kW", "n) Pre-existing RTS:", "3 kW of overall RTS plant size.", A)
node(D, "6(f)", "minimum technical specifications", "f) Minimum Technical Specifications: The Ministry shall identify", "at the time of inspection.", A)
node(D, "6(h)", "feasibility: deemed approval up to 10 kW per ROC Rules", "h) Feasibility Approval:", "as per extant state regulations.", A)
node(D, "6(l)", "metering arrangements covered", "l) Meter Installation and Agreement:", "shall be covered under the scheme.", A)
node(D, "6(m)", "metering: smart net meters via AMISP", "m) Metering in AMISP Areas:", "(Advance Metering Infrastructure Service Provider).", A)
node(D, "Annexure-1", "Phase-II claims cut-off (October 2024) and rates", "| Note: all applications received prior to launch", "The claims received after October 2024 will not be entertained. |", A)
amd = "2025-07-07"
amd_note = "Para-wise amendment OM F.no.318/140/2024 dated 07.07.2025 bundled at the front of this file; clause_ref is its Sl. No."
node(D, "Amendment-i", "additional state subsidy (amended 5(i))", "Additional State/UTsubsidyshouldbe", "updated on the National portal.", date=amd, conf="low", note=amd_note + "; two-column OCR interleaves existing and amended text")
node(D, "Amendment-ii", "Phase-II claims cut-off extended to 31.12.2025", "submitted under the Phase IIofrooftop", "PMSG: MBY in the future.", date=amd, conf="low", note=amd_note + "; two-column OCR interleaves existing and amended text")
node(D, "Amendment-iii", "technical specifications amendable prospectively", "6(f): The Ministry shall identify the", "atthetime ofinspection.", date=amd, conf="low", note=amd_note + "; two-column OCR interleaves existing and amended text")

D = "IN-C1-005"
node(D, "3", "CFA to developers/promoters for GHS/RWA common areas", "3.\nRepresentations have been received", "authenticate\nthe subsidy claimant.", conf="medium")

D = "IN-C2-004"
node(D, "1.5.1", "ALMM minimum module efficiency (rooftop 19.5%)", "1.5.1Onlysuchmodelsof Solar", "Solar Lighting\n19.0%", conf="medium")
node(D, "1.6", "ALMM Order in abeyance FY 2023-24", "1.6.It is reiterated", "24.", conf="medium")

D = "IN-C2-003"
node(D, "1", "ALMM: 09.02.2024 OM held in abeyance", "The undersigned is directed to convey that the O.M. of even no. dated 9th February, 2024", "held in abeyance till further orders.", conf="medium")
node(D, "encl.a-b", "ALMM re-imposed 1.4.2024; applies to subsidised rooftops only (09.02.2024 OM)", "a) The ALMM [Approved List of Models & Manufacturers] for Solar PV Modules, is being", "set up their own capacity.", date="2024-02-09", conf="medium",
     note="Enclosed OM dated 09.02.2024 (page 2 of the file); paragraph letters a) and b)")

D = "IN-C2-002"
node(D, "1", "ALMM for modules effective 1 April 2024", "Vide MNRE's Order of even no.dated 10\" March 2023", "comeintoeffectfrom1st April, 2024.", conf="medium")

D = "IN-C2-007"
node(D, "4", "ALMM efficiency thresholds amended (rooftop 19.50% unchanged; off-grid <200 Wp 18%)", "Accordingly, it has been decided to amend the aforesaid module efficiency thresholds", "Category-IV", conf="medium")

D = "IN-C2-006"
node(D, "8", "ALMM List-II cells for net-metering projects commissioned on/after 1 June 2026", "These Net_Metering and Open", "solar PV cells from ALMM List-II.", conf="medium")

D = "IN-C2-005"
node(D, "2(b)", "DCR verification via portal mandatory for PMSG from 1.12.2024", "b) From 1 st December 2024 onwards", "PM-KUSUM.", conf="medium")

D = "IN-C2-001"
node(D, "2", "ALMM List-I enlistment efficiency criteria (restated)", "2. This Ministry vide its o.M. No. 283/22/2023-GRID SOLAR/Pt dated 10.05.2023", "minimum module efficlencY:", conf="low", note="OCR of threshold table illegible")

# ======================= EDGES =======================
# --- MH regulation chain (explicit substitution / introduction language) ---
Q3, Q2 = ("MH-C3-003", "--- Page 13 ---"), ("MH-C3-002", "--- Page 6 ---")
edge("MH-C3-001#cl-2.1(j)", "MH-C3-003#cl-2.1(j)", "supersedes", *Q3[:1], "Substitution of Regulation 2.1 (j) of the Principal Regulations:—", "Principal Regulations:—", "high", anchor=Q3[1])
edge("MH-C3-001#cl-8.3", "MH-C3-003#cl-8.3", "supersedes", "MH-C3-003", "Substitution of Regulation 8.3 of the Principal Regulations:—", "ascertained by the Distribution Licensee.”", "high", anchor=Q3[1])
edge("MH-C3-001#cl-8.11", "MH-C3-003#cl-8.11", "supersedes", "MH-C3-003", "Substitution of Regulation 8.11 of the Principal Regulations:—", "installed by the Distribution Licensee.”", "high", anchor=Q3[1])
edge("MH-C3-001#cl-9.5", "MH-C3-003#cl-9.5", "supersedes", "MH-C3-003", "Substitution of Regulation 9.5 of the Principal Regulations:—", "delay in performing the activity.”", "high", anchor=Q3[1])
edge("MH-C3-001#cl-11.5", "MH-C3-003#cl-11.5", "amends", "MH-C3-003", "Introduction of 2nd Proviso to Regulation 11.5 of the Principal Regulations:—", "reach 5000 MW:", "high", anchor=Q3[1])
edge("MH-C3-001#cl-12.1", "MH-C3-003#cl-12.1", "supersedes", "MH-C3-003", "Substitution of Regulation 12 and 12.1 of the Principal Regulations:—", "Purchase Agreement :", "high", anchor=Q3[1])
edge("MH-C3-001#cl-Annexure-1.h", "MH-C3-003#cl-Annexure-1.h", "supersedes", "MH-C3-003", "Substitution of Clause 1(h) of Annexure-1 of the Principal Regulations:—", "synchronized with the distribution\nnetwork.”", "high", anchor=Q3[1])
edge("MH-C3-003#cl-2.1(j)", "MH-C3-002#cl-2.1(j)", "amends", "MH-C3-002", "Introduction of 4th and 5th proviso to Regulation 2.1 (j) of the Principal Regulations :—", "Arrangement:", "high", anchor=Q2[1])
edge("MH-C3-003#cl-8.11", "MH-C3-002#cl-8.11", "supersedes", "MH-C3-002", "Substitution of Regulation 8.11 of the Amendment Regulations :—", "Licensee.”", "high", anchor=Q2[1])
edge("MH-C3-001#cl-9.7", "MH-C3-002#cl-9.7", "supersedes", "MH-C3-002", "Substitution of Regulation 9.7 of the Principal Regulations : —", "chronological order of seniority.”", "high", anchor=Q2[1])
edge("MH-C3-001#cl-Annexure-1.c", "MH-C3-002#cl-Annexure-1.c", "supersedes", "MH-C3-002", "Substitution of Clause C of Annexure-1 of the Principal Regulations :—", "proposal is technically\nfeasible:", "high", anchor=Q2[1])
# --- MH implicit / order-based ---
edge("MH-C3-001#cl-11.4(d)", "MH-C3-004#cl-7.13.79", "partially_supersedes", "MH-C3-004", "7.13.79 Hence, the Commission further rules", "slot wise banking requirement.", "low",
     reason="Tariff order (not a regulation amendment) directs that for LT-residential RTS consumers net-metering credits apply across all hours without ToD-slot-wise banking, displacing the off-peak treatment of Reg 11.4(d) for that class during the 5th Control Period; no substitution language.")
edge("MH-C5-001#cl-2.1", "MH-C3-003#cl-2.1(j)", "supersedes", "MH-C3-003", "Substitution of Regulation 2.1 (j) of the Principal Regulations:—", "Principal Regulations:—", "low", anchor=Q3[1],
     reason="CC/322 restates the 2019 definition (<1 MW); the regulation it restates was substituted in 2023. No MSEDCL circular in the corpus withdraws CC/322 clause 2.1.")
edge("MH-C5-001#cl-5.6", "MH-C5-006#cl-3", "partially_supersedes", "MH-C5-006", "3. In cases, where RTS application received with pending arrears", "New Connection System.", "low",
     reason="2024 MSEDCL letter lets PMSG applications with arrears be auto-processed (arrears still recovered before net meter issue, p.2); no express withdrawal of CC/322 5.6, and the underlying MERC Reg 6.6 is not amended in the corpus.")
edge("MH-C5-005#cl-3.2", "IN-C1-001#cl-5(e)", "partially_supersedes", "IN-C1-001", "Rooftop Solar Phase II Programme since 2019", "Muft Bijli Yojana.", "low", anchor="--- Page 3 ---",
     reason="Central Phase-II CFA slab (as implemented by MSEDCL CC/331) displaced for new applications by PMSG CFA; MNRE text subsumes Phase-II, MSEDCL text never withdrawn.")
edge("MH-C6-001#cl-GCR-2", "IN-C1-001#cl-5(e)", "partially_supersedes", "IN-C1-001", "Rooftop Solar Phase II Programme since 2019", "Muft Bijli Yojana.", "low", anchor="--- Page 3 ---",
     reason="Undated MEDA FAQ states Phase-II 40%/20% subsidy; superseded in substance by PMSG CFA, not by any MEDA text.")

# --- RJ chain ---
A5 = "--- Page 5 ---"
edge("RJ-C3-001#cl-2", "RJ-C3-002#cl-6.1", "partially_supersedes", "RJ-C3-002", "3.4 These Regulations shall be applicable to all Grid interactive", "amendments thereof:", "medium",
     reason="2021 Regulations apply to systems commissioned on/after 1 July 2021 and coexist with the 2015 Regulations (Reg 1.4); no repeal clause. DT limit 30% -> 50% for new systems.")
edge("RJ-C3-001#cl-3", "RJ-C3-002#cl-7.2", "partially_supersedes", "RJ-C3-002", "3.4 These Regulations shall be applicable to all Grid interactive", "amendments thereof:", "medium",
     reason="Capacity cap 80% -> 100% of sanctioned load/CD for systems commissioned on/after 1 July 2021; 2015 Regulations continue for earlier systems.")
edge("RJ-C3-001#cl-6", "RJ-C3-002#cl-12.6.1(a)", "partially_supersedes", "RJ-C3-002", "Provided that, even in case of Domestic consumers having existing Net Metering", "immediately succeeding billing cycle:", "medium",
     reason="2021 Reg 12.6.1(a) proviso expressly extends the new surplus-purchase rate to domestic installations governed by the 2015 Regulations.")
edge("RJ-C3-001#cl-10", "RJ-C3-002#cl-11.10", "partially_supersedes", "RJ-C3-002", "3.4 These Regulations shall be applicable to all Grid interactive", "amendments thereof:", "low",
     reason="Check meter optional up to 250 kW (2015) vs consumer-installed check meter (2021) for new systems; inferred from applicability clause only.")
edge("RJ-C3-002#cl-6.1", "RJ-C3-003#cl-6.1", "supersedes", "RJ-C3-003", "The existing sub-regulation 6.1 shall be substituted with the following:", "capacity of\nsuch distribution transformer", "high", anchor=A5)
edge("RJ-C3-002#cl-10.14.3", "RJ-C3-003#cl-10.14.3", "supersedes", "RJ-C3-003", "The existing sub-regulation 10.14.3 shall be substituted with the following:", "capacity permissible under regulation 10.14.2 above.", "high", anchor=A5)
edge("RJ-C3-002#cl-12.5.2", "RJ-C3-003#cl-12.5.2", "supersedes", "RJ-C3-003", "(1) The existing main provision and first proviso of sub-regulation 12.5.2 shall be", "plus an incentive of 40%.", "high", anchor=A5)
edge("RJ-C3-002#cl-12.5.6", "RJ-C3-003#cl-12.5.6", "supersedes", "RJ-C3-003", "(2) The existing provision of sub-regulation 12.5.6 shall be substituted with the", "contracted AC capacity.", "high", anchor=A5)
edge("RJ-C3-002#cl-12.6.1(a)", "RJ-C3-003#cl-12.6.1(a)", "supersedes", "RJ-C3-003", "(3) The existing main provisions and first proviso of sub-regulation 12.6.1 (a) and the", "substituted with the following:", "high", anchor=A5)
edge("RJ-C3-002#cl-12.6.1(d)", "RJ-C3-003#cl-12.6.1(d)", "supersedes", "RJ-C3-003", "(3) The existing main provisions and first proviso of sub-regulation 12.6.1 (a) and the", "substituted with the following:", "high", anchor=A5)
edge("RJ-C3-002#cl-12.6.1(b)", "RJ-C3-003#cl-12.6.1(b)", "supersedes", "RJ-C3-003", "(4) The existing First Proviso to sub-regulation 12.6.1 (b) shall be substituted with the", "from all sources.”", "high", anchor=A5)
edge("RJ-C3-002#cl-15.2", "RJ-C3-003#cl-15.2", "amends", "RJ-C3-003", "A new Third proviso shall be added below the existing main sub-regulation 15.2 as", "public undertakings of the State Govt.”", "high", anchor=A5)
edge("RJ-C3-002#cl-3.2", "RJ-C3-004#cl-12", "amends", "RJ-C3-004", "12. In view of above, the Commission under its power", "for all\ncategories of the consumers.", "medium",
     reason="Suo-motu direction under Reg 19 (power to give directions), implementing Reg 3.2 proviso; it raises the net-metering limit from the 500 kW set by an earlier 07.09.2021 order that is not in the corpus.")
A6 = "RAJASTHAN STATE ELECTRICITY REGULATORY COMMISSION"
edge("RJ-C3-002#cl-8.8", "RJ-C3-005#cl-8.8", "supersedes", "RJ-C3-005", "(1) The existing sub regulation 8.8 shall be substituted with the following:", "proposal is technically feasible.", "high", anchor=A6)
edge("RJ-C3-002#cl-8.12", "RJ-C3-005#cl-8.12", "supersedes", "RJ-C3-005", "(2) The existing sub regulation 8.12 shall be substituted with the following:", "within fifteen\ndays from the date of submission of the installation certificate.", "high", anchor=A6)
edge("RJ-C3-003#cl-12.6.1(a)", "RJ-C3-005#cl-12.6.1(a)", "amends", "RJ-C3-005", "A new Third Proviso shall be added below the existing Second Proviso to the sub-regulation", "12.6.1(a)of the main sub regulation 12.6 as under:", "high", anchor=A6)

# --- IN: ROC Rules ---
A = "MINISTRY OF POWER"
edge("IN-C3-002#cl-11(7)", "IN-C3-001#cl-11(7)", "supersedes", "IN-C3-001", "(i) for sub-rule (7), the following sub-rule shall be substituted, namely:-\n“(7) For installation", "presumed that the proposal is technically feasible.", "high", anchor=A)
edge("IN-C3-002#cl-11(7)", "IN-C3-001#cl-11(7A)", "supersedes", "IN-C3-001", "(i) for sub-rule (7), the following sub-rule shall be substituted, namely:-\n“(7) For installation", "presumed that the proposal is technically feasible.", "high", anchor=A)
edge("IN-C3-002#cl-11(8)", "IN-C3-001#cl-11(8)", "supersedes", "IN-C3-001", "(ii) for sub-rule (8), the following sub-rule shall be substituted, namely:-", "(8) subject to sub-rule (7A)", "high", anchor=A)
edge("IN-C3-002#cl-11(9)", "IN-C3-001#cl-11(9)", "supersedes", "IN-C3-001", "(iii) for sub-rule (9), the following sub-rule shall be substituted, namely:-", "submission of the installation certificate.", "high", anchor=A)

# --- IN: CFA scheme ---
edge("IN-C1-002#cl-2", "IN-C1-003#cl-3", "partially_supersedes", "IN-C1-003", "The previous scheme of Phase-II of the Grid Connected Rooftop Solar", "i.e.,13.02.2024.", "medium",
     reason="Phase-II deemed subsumed from 13.02.2024; applications received before that date stay on Phase-II CFA (Annexure I), so displacement is prospective, not a repeal of the 2019 OM.")
edge("IN-C1-002#cl-2", "IN-C1-001#cl-5(e)", "partially_supersedes", "IN-C1-001", "Rooftop Solar Phase II Programme since 2019", "Muft Bijli Yojana.", "medium", anchor="--- Page 3 ---",
     reason="Same subsumption, stated in the PMSG operational guidelines; Phase-II claims governed by Phase-II guidelines (para 4(d)).")
edge("IN-C1-009#cl-2.iii", "IN-C1-001#cl-6(h)", "partially_supersedes", "IN-C1-001", "h) Feasibility Approval:", "as per extant state regulations.", "low", anchor="--- Page 3 ---",
     reason="Phase-II national-portal procedure (15 working-day feasibility) replaced in substance by PMSG deemed approval up to 10 kW; no express reference to the 2022 OM.")
edge("IN-C1-001#cl-5(f)", "IN-C1-005#cl-3", "amends", "IN-C1-005", "The clause 5(f) of the above-mentioned guidelines states", "handed over to the GHS/RWA/AOAs/", "high")
edge("IN-C1-001#cl-5(i)", "IN-C1-001#cl-Amendment-i", "amends", "IN-C1-001", "Considering the feedback from the implementing agencies", "amendments\nin theaforementioned Guidelines asper attached Annexure is issued.", "high")
edge("IN-C1-001#cl-Annexure-1", "IN-C1-001#cl-Amendment-ii", "supersedes", "IN-C1-001", "Considering the feedback from the implementing agencies", "amendments\nin theaforementioned Guidelines asper attached Annexure is issued.", "high")
edge("IN-C1-001#cl-6(f)", "IN-C1-001#cl-Amendment-iii", "amends", "IN-C1-001", "Considering the feedback from the implementing agencies", "amendments\nin theaforementioned Guidelines asper attached Annexure is issued.", "high")

# --- IN: ALMM ---
edge("IN-C2-004#cl-1.5.1", "IN-C2-007#cl-4", "amends", "IN-C2-007", "Accordingly, it has been decided to amend the aforesaid module efficiency thresholds", "for ALMM enlistmentasfollows:", "high",
     reason="Only Category-III changes (off-grid <200 Wp, 18%); rooftop Category-II stays 19.5%. An intermediate amendment OM of 22.03.2024 (adds CdTe thresholds) is cited but not in the corpus.")
edge("IN-C2-003#cl-encl.a-b", "IN-C2-003#cl-1", "supersedes", "IN-C2-003", "The undersigned is directed to convey that the O.M. of even no. dated 9th February, 2024", "held in abeyance till further orders.", "medium",
     reason="Suspension ('held in abeyance till further orders'), not repeal.")
edge("IN-C2-004#cl-1.6", "IN-C2-002#cl-1", "supersedes", "IN-C2-002", "Vide MNRE's Order of even no.dated 10\" March 2023", "comeintoeffectfrom1st April, 2024.", "medium",
     reason="Abeyance for FY 2023-24 ends; ALMM for modules in effect from 1 April 2024 (the abeyance was time-limited by its own terms).")
edge("IN-C2-003#cl-1", "IN-C2-002#cl-1", "partially_supersedes", "IN-C2-002", "Vide MNRE's Order of even no.dated 10\" March 2023", "comeintoeffectfrom1st April, 2024.", "low",
     reason="29.03.2024 OM confirms ALMM effective 1.4.2024 despite the 15.02.2024 abeyance of the 09.02.2024 OM; it does not mention either February OM.")

# ======================= DOCUMENT SUPERSESSIONS =======================
doc_sup = [
    {"doc_from": "MERC (Net Metering for Rooftop Solar Photo Voltaic Systems) Regulations, 2015 [not in corpus]",
     "doc_to": "MH-C3-001", "type": "repeal",
     "evidence_quote": cut("MH-C3-001", "Save as otherwise provided in these Regulations", "are hereby repealed:"),
     "confidence": "high",
     "note": "Saving: systems under the 2015 Regulations continue under them for the validity of their agreements. Corpus MSEDCL circulars MH-C5-003 (2016) and MH-C5-004 (CC/310, 2018) implement the repealed 2015 Regulations via CC/258; no express withdrawal of those circulars is in the corpus."},
    {"doc_from": "RJ-C3-001", "doc_to": "RJ-C3-002", "type": "prospective_replacement_no_repeal",
     "evidence_quote": cut("RJ-C3-002", "1.4 These Regulations shall remain in force along with", "subsequent amendments\nthereof."),
     "confidence": "medium",
     "note": "No repeal clause: the 2021 Regulations coexist with the 2015 Regulations, which keep governing systems commissioned up to 30.06.2021 (Reg 1.4, 3.4); some 2021 settlement provisions expressly extend to 2015-era installations."},
    {"doc_from": "IN-C1-002", "doc_to": "IN-C1-003", "type": "scheme_subsumption",
     "evidence_quote": cut("IN-C1-003", "The previous scheme of Phase-II of the Grid Connected Rooftop Solar", "i.e.,13.02.2024."),
     "confidence": "medium",
     "note": "Phase-II programme (incl. IN-C1-002 CFA OM and IN-C1-009 procedure OM) subsumed into PMSG from 13.02.2024; Phase-II applications before that date keep Phase-II CFA. Not a repeal."},
]

out = {"generated_by": "Claude Opus (Claude Code agent), blind to gold graph, from corpus text r2",
       "generated_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
       "nodes": nodes, "edges": edges, "document_supersessions": doc_sup}

if FAILS:
    print("\n".join(FAILS)); raise SystemExit(1)
# self-check: every snippet/quote is verbatim, <=600 chars, edges run older->newer by effective date
for n in nodes:
    assert n["snippet"] in TXT[n["doc_id"]] and len(n["snippet"]) <= 600, n["node_id"]
for e in edges:
    a, b = IDX[e["from_node"]]["effective_date"], IDX[e["to_node"]]["effective_date"]
    assert not (a and b) or a <= b, (e["from_node"], e["to_node"], a, b)
    assert len(e["evidence_quote"]) <= 600

(BASE / "registry_real.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
from collections import Counter
print("nodes", len(nodes), Counter(n["jurisdiction"] for n in nodes))
print("edges", len(edges), Counter(IDX[e["to_node"]]["jurisdiction"] for e in edges), Counter(e["type"] for e in edges), Counter(e["confidence"] for e in edges))
