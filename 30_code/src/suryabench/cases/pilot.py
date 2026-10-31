"""Construction of the 10-Case Hardware and Benchmark Pilot (protocol §7A, §1.4)."""

from suryabench.applicability.schema import CaseFacts
from suryabench.cases.schema import (
    ApplicableRuleReference,
    BenchmarkCase,
    CaseInputs,
    ExpectedAnswer,
    FaultEvent,
    GroundTruthProvenance,
    NonFaultOpportunity,
)
from suryabench.cases.validator import validate_benchmark_suite
from suryabench.core.enums import (
    AlmmStatus,
    ConfidenceLevel,
    ConsumerCategory,
    DiscomCode,
    ExpectedDecision,
    FaultClass,
    MeteringMode,
    PremisesType,
    StateCode,
)

PILOT_CORPUS_VERSION = "SuryaBench-Corpus-2026.11"


def get_pilot_cases() -> list[BenchmarkCase]:
    """Construct the 10 canonical pilot cases spanning all specification partitions."""
    cases = [
        # Case 1: Clean Nominal 1 (4 kW on 5 kW load)
        BenchmarkCase(
            case_id="MH-PILOT-001",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=5.0,
                connected_load_kw=5.0,
                proposed_capacity_kw=4.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                install_before_feasibility=False,
                case_date="2024-06-15",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nConsumer No: 021548796321\nName: Rajesh Sharma\nCategory: Residential (LT-I)\nSanctioned Load: 5.0 kW\nConnected Load: 5.0 kW\nTariff: LT-I Domestic",
                proposal="INSTALLER PROPOSAL - SunPower Solutions\nClient: Rajesh Sharma\nSystem Capacity: 4.0 kWp Grid-Tied Solar PV\nModules: 540W Mono-PERC (ALMM Listed, DCR Compliant)\nInverter: 4.0 kW Grid-Interactive Inverter",
                portal_state="MSEDCL RTS PORTAL\nStatus: New Application Draft\nFeasibility Stage: Pending Submission",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="MH-C3-001#cl-6.2",
                    clause="6.2",
                    effective_date="2019-12-30",
                    jurisdiction="MH",
                    applicability_basis="Sanctioned load upper limit for net metering in Maharashtra",
                ),
                ApplicableRuleReference(
                    rule_id="IN-C1-001#cl-4.1",
                    clause="5(e)",
                    effective_date="2024-02-13",
                    jurisdiction="IN",
                    applicability_basis="PM Surya Ghar Central Financial Assistance subsidy slabs",
                ),
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage=None,
                root_cause=None,
                next_action="Submit technical feasibility application on MSEDCL portal",
                prohibited_actions=["Install rooftop solar before technical feasibility sanction"],
                computed=[{"cfa_subsidy_inr": 78000, "permissible_capacity_kw": 5.0}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="CLEAN",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-001#nfo-1",
                    case_id="MH-PILOT-001",
                    target_property="jurisdiction",
                    claim_text="MSEDCL and MERC regulations apply to Maharashtra electricity consumers",
                ),
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-001#nfo-2",
                    case_id="MH-PILOT-001",
                    target_property="currency",
                    claim_text="PM Surya Ghar guidelines of 2024 govern CFA for post-February 2024 applications",
                ),
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-001#nfo-3",
                    case_id="MH-PILOT-001",
                    target_property="capacity_cap",
                    claim_text="Proposed 4 kW is within 100% of the 5 kW sanctioned load",
                ),
            ],
        ),
        # Case 2: Clean Nominal 2 (3 kW on 3 kW load)
        BenchmarkCase(
            case_id="MH-PILOT-002",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=3.0,
                connected_load_kw=3.0,
                proposed_capacity_kw=3.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                install_before_feasibility=False,
                case_date="2024-06-15",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nConsumer No: 021548796322\nCategory: Residential\nSanctioned Load: 3.0 kW\nConnected Load: 3.0 kW",
                proposal="INSTALLER PROPOSAL\nSystem Capacity: 3.0 kWp Grid-Tied Solar PV\nModules: ALMM Listed, DCR Compliant",
                portal_state="MSEDCL RTS PORTAL\nStatus: Application Draft",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="MH-C3-001#cl-6.2",
                    clause="6.2",
                    effective_date="2019-12-30",
                    jurisdiction="MH",
                    applicability_basis="Sanctioned load upper limit",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage=None,
                root_cause=None,
                next_action="Submit technical feasibility application",
                prohibited_actions=[],
                computed=[{"cfa_subsidy_inr": 78000, "permissible_capacity_kw": 3.0}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="CLEAN",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-002#nfo-1",
                    case_id="MH-PILOT-002",
                    target_property="capacity_cap",
                    claim_text="Proposed 3 kW exactly equals 100% sanctioned load",
                )
            ],
        ),
        # Case 3: F5 Near-Miss 1 (5.2 kW on 5.0 kW load)
        BenchmarkCase(
            case_id="MH-PILOT-003",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=5.0,
                connected_load_kw=5.0,
                proposed_capacity_kw=5.2,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                case_date="2024-06-15",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nSanctioned Load: 5.0 kW\nConnected Load: 5.0 kW",
                proposal="INSTALLER PROPOSAL\nSystem Capacity: 5.2 kWp Grid-Tied Solar PV",
                portal_state="MSEDCL RTS PORTAL\nStatus: Feasibility Query Raised",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="MH-C3-001#cl-6.2",
                    clause="6.2",
                    effective_date="2019-12-30",
                    jurisdiction="MH",
                    applicability_basis="Net metering capacity cannot exceed 100% of sanctioned load",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage="Technical Feasibility",
                root_cause="Proposed 5.2 kW capacity exceeds 5.0 kW sanctioned load limit",
                next_action="Apply for sanctioned load enhancement to 6.0 kW or reduce solar capacity to 5.0 kW",
                prohibited_actions=[
                    "Proceeding with interconnection at 5.2 kW without load enhancement"
                ],
                computed=[{"permissible_capacity_kw": 5.0, "excess_capacity_kw": 0.2}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="F5",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-003#fe-1",
                    case_id="MH-PILOT-003",
                    fault_class=FaultClass.F5,
                    gold_trigger="proposed_capacity_kw (5.2) > sanctioned_load_kw (5.0)",
                    gold_evidence=["MH-C3-001#cl-6.2"],
                    expected_behavior="Flag proposed capacity as exceeding sanctioned load limit and require load enhancement",
                )
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-003#nfo-1",
                    case_id="MH-PILOT-003",
                    target_property="jurisdiction",
                    claim_text="MERC regulations correctly govern Maharashtra",
                )
            ],
        ),
        # Case 4: F5 Near-Miss 2 (Commercial consumer claiming residential CFA subsidy)
        BenchmarkCase(
            case_id="MH-PILOT-004",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.COMMERCIAL,
                sanctioned_load_kw=10.0,
                connected_load_kw=10.0,
                proposed_capacity_kw=8.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                case_date="2024-06-15",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nCategory: Commercial (LT-II)\nSanctioned Load: 10.0 kW",
                proposal="INSTALLER PROPOSAL\nCapacity: 8.0 kWp\nClaim: Central CFA Subsidy",
                portal_state="MSEDCL RTS PORTAL\nStatus: Subsidy Eligibility Check",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="IN-C1-001#cl-4.1",
                    clause="5(d)",
                    effective_date="2024-02-13",
                    jurisdiction="IN",
                    applicability_basis="Clause 5(d) explicitly excludes non-residential and commercial consumers from CFA",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage="Subsidy Sanction",
                root_cause="Commercial consumer category is ineligible for Central Financial Assistance",
                next_action="Remove subsidy claim from application and proceed under commercial net metering",
                prohibited_actions=["Disbursing CFA subsidy to commercial entity"],
                computed=[{"cfa_subsidy_inr": 0}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="F5",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-004#fe-1",
                    case_id="MH-PILOT-004",
                    fault_class=FaultClass.F5,
                    gold_trigger="consumer_category == 'commercial' and subsidy_claimed == True",
                    gold_evidence=["IN-C1-001#cl-4.1"],
                    expected_behavior="Reject CFA subsidy claim due to commercial consumer ineligibility under clause 5(d)",
                )
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-004#nfo-1",
                    case_id="MH-PILOT-004",
                    target_property="capacity_cap",
                    claim_text="8 kW capacity is valid under 10 kW commercial sanctioned load",
                )
            ],
        ),
        # Case 5: F3 Currency Trap 1 (Generator cites superseded 2019 Phase-II subsidy)
        BenchmarkCase(
            case_id="MH-PILOT-005",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=4.0,
                connected_load_kw=4.0,
                proposed_capacity_kw=3.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                case_date="2024-06-15",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nSanctioned Load: 4.0 kW\nApplication Date: 2024-06-15",
                proposal="INSTALLER PROPOSAL\nSystem: 3.0 kWp Residential Solar\nSeeking: Government Subsidy",
                portal_state="PM SURYA GHAR NATIONAL PORTAL\nRegistered: June 2024",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="IN-C1-001#cl-4.1",
                    clause="5(e)",
                    effective_date="2024-02-13",
                    jurisdiction="IN",
                    applicability_basis="PM Surya Ghar fixed CFA (Rs 78,000) supersedes Phase-II 2019 benchmark rules",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage=None,
                root_cause=None,
                next_action="Disburse CFA under PM Surya Ghar 2024 slabs",
                prohibited_actions=["Applying superseded 2019 40% benchmark cost subsidy formula"],
                computed=[{"cfa_subsidy_inr": 78000}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_supersession", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="F3",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-005#fe-1",
                    case_id="MH-PILOT-005",
                    fault_class=FaultClass.F3,
                    gold_trigger="reliance_on_node('IN-C1-002#cl-2') after 2024-02-13",
                    gold_evidence=["IN-C1-001#cl-4.1", "IN-C1-002#cl-2"],
                    expected_behavior="Apply PM Surya Ghar 2024 CFA guidelines; reject superseded 2019 Phase-II formula",
                )
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-005#nfo-1",
                    case_id="MH-PILOT-005",
                    target_property="jurisdiction",
                    claim_text="Central MNRE subsidy applies nationally to residential consumers",
                )
            ],
        ),
        # Case 6: F3 Currency Trap 2 (Rajasthan 2015 80% cap vs 2021 100% cap)
        BenchmarkCase(
            case_id="MH-PILOT-006",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.RJ,
                discom=DiscomCode.JVVNL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=5.0,
                connected_load_kw=5.0,
                proposed_capacity_kw=5.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                case_date="2022-04-10",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - JVVNL (Jaipur Discom)\nSanctioned Load: 5.0 kW\nApplication Date: 2022-04-10",
                proposal="INSTALLER PROPOSAL\nCapacity: 5.0 kWp Net Metering Solar",
                portal_state="JVVNL SOLAR PORTAL\nStatus: Feasibility Assessment",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="RJ-C3-002#cl-7.2",
                    clause="7.2",
                    effective_date="2021-06-15",
                    jurisdiction="RJ",
                    applicability_basis="RERC 2021 regulations allow up to 100% of sanctioned load, superseding 2015 80% cap",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage=None,
                root_cause=None,
                next_action="Approve feasibility application at 5.0 kW under RERC 2021 regulations",
                prohibited_actions=[
                    "Restricting capacity to 4.0 kW (80%) under repealed 2015 regulations"
                ],
                computed=[{"permissible_capacity_kw": 5.0}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_supersession", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="F3",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-006#fe-1",
                    case_id="MH-PILOT-006",
                    fault_class=FaultClass.F3,
                    gold_trigger="reliance_on_node('RJ-C3-001#cl-3.1') after 2021-06-15",
                    gold_evidence=["RJ-C3-002#cl-7.2", "RJ-C3-001#cl-3.1"],
                    expected_behavior="Approve 5.0 kW under RERC 2021; do not cap at 4.0 kW (80%) using superseded 2015 rules",
                )
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-006#nfo-1",
                    case_id="MH-PILOT-006",
                    target_property="jurisdiction",
                    claim_text="JVVNL is bound by RERC regulations in Rajasthan",
                )
            ],
        ),
        # Case 7: F2 Jurisdiction Trap (Jaipur consumer assessed against Maharashtra MERC rule)
        BenchmarkCase(
            case_id="MH-PILOT-007",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.RJ,
                discom=DiscomCode.JVVNL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=10.0,
                connected_load_kw=10.0,
                proposed_capacity_kw=8.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=False,
                application_stage="technical_feasibility",
                case_date="2023-01-10",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - JAIPUR VIDYUT VITRAN NIGAM LTD (JVVNL)\nAddress: Vaishali Nagar, Jaipur, Rajasthan\nSanctioned Load: 10.0 kW",
                proposal="INSTALLER PROPOSAL\nCapacity: 8.0 kWp Grid-Tied Solar System",
                portal_state="DISCOM PORTAL: JVVNL RajSolar",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="RJ-C3-002#cl-7.2",
                    clause="7.2",
                    effective_date="2021-06-15",
                    jurisdiction="RJ",
                    applicability_basis="Governed by RERC (Rajasthan), not MERC (Maharashtra)",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage=None,
                root_cause=None,
                next_action="Process under RERC 2021 regulations and JVVNL interconnection rules",
                prohibited_actions=[
                    "Applying Maharashtra MERC regulations or MSEDCL circulars to Rajasthan connection"
                ],
                computed=[{"permissible_capacity_kw": 10.0}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="F2",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-007#fe-1",
                    case_id="MH-PILOT-007",
                    fault_class=FaultClass.F2,
                    gold_trigger="citation_of_jurisdiction('MH') when case.state == 'RJ'",
                    gold_evidence=["RJ-C3-002#cl-7.2"],
                    expected_behavior="Cite RERC regulations for Rajasthan; reject Maharashtra MERC rules",
                )
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-007#nfo-1",
                    case_id="MH-PILOT-007",
                    target_property="currency",
                    claim_text="RERC 2021 regulations are active in 2023",
                )
            ],
        ),
        # Case 8: F6 Input-Binding Trap (Sanctioned Load 5 kW vs Connected Load 8 kW)
        BenchmarkCase(
            case_id="MH-PILOT-008",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=5.0,
                connected_load_kw=8.0,
                proposed_capacity_kw=7.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                case_date="2024-06-15",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nSanctioned Contract Demand / Load: 5.0 kW\nTotal Connected Apparatus Load: 8.0 kW",
                proposal="INSTALLER PROPOSAL\nCapacity: 7.0 kWp Solar PV (Based on Connected Load of 8 kW)",
                portal_state="MSEDCL RTS PORTAL\nStatus: Scrutiny",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="MH-C3-001#cl-6.2",
                    clause="6.2",
                    effective_date="2019-12-30",
                    jurisdiction="MH",
                    applicability_basis="Clause 6.2 restricts capacity to Sanctioned Load (5 kW), not Connected Load (8 kW)",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage="Technical Feasibility",
                root_cause="Proposed 7 kW exceeds Sanctioned Load of 5 kW (statutory limit is bound to Sanctioned Load, not Connected Load)",
                next_action="Enhance Sanctioned Load from 5 kW to 7 kW or reduce solar plant size to 5 kW",
                prohibited_actions=[
                    "Binding capacity limit to Connected Load instead of Sanctioned Load"
                ],
                computed=[{"permissible_capacity_kw": 5.0, "sanctioned_load_kw": 5.0}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="F6",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-008#fe-1",
                    case_id="MH-PILOT-008",
                    fault_class=FaultClass.F6,
                    gold_trigger="binding_field == 'connected_load_kw' instead of 'sanctioned_load_kw'",
                    gold_evidence=["MH-C3-001#cl-6.2"],
                    expected_behavior="Bind permissible net metering capacity to Sanctioned Load (5 kW); reject proposal of 7 kW",
                )
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-008#nfo-1",
                    case_id="MH-PILOT-008",
                    target_property="jurisdiction",
                    claim_text="MERC Clause 6.2 correctly governs Maharashtra",
                )
            ],
        ),
        # Case 9: MULTI Multi-Fault (F3 Currency + F5 Applicability)
        BenchmarkCase(
            case_id="MH-PILOT-009",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=4.0,
                connected_load_kw=4.0,
                proposed_capacity_kw=6.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                case_date="2024-07-01",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nSanctioned Load: 4.0 kW\nDate: July 2024",
                proposal="INSTALLER PROPOSAL\nCapacity: 6.0 kWp\nSubsidy Claim: Seeking 40% Benchmark Subsidy under 2019 Phase-II Rules",
                portal_state="MSEDCL RTS PORTAL\nStatus: Feasibility and Subsidy Scrutiny",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="MH-C3-001#cl-6.2",
                    clause="6.2",
                    effective_date="2019-12-30",
                    jurisdiction="MH",
                    applicability_basis="Capacity cap violation (6 kW > 4 kW load)",
                ),
                ApplicableRuleReference(
                    rule_id="IN-C1-001#cl-4.1",
                    clause="5(e)",
                    effective_date="2024-02-13",
                    jurisdiction="IN",
                    applicability_basis="PM Surya Ghar fixed CFA supersedes Phase-II 2019 benchmark rules",
                ),
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage="Technical Feasibility & Subsidy",
                root_cause="Proposed 6 kW exceeds 4 kW load cap (F5) and proposal cites superseded 2019 subsidy formula (F3)",
                next_action="Reduce solar system size to 4 kW and calculate CFA using PM Surya Ghar 2024 fixed slabs",
                prohibited_actions=[
                    "Approving 6 kW on 4 kW load",
                    "Calculating subsidy using 2019 benchmark percentages",
                ],
                computed=[{"permissible_capacity_kw": 4.0, "cfa_subsidy_inr": 78000}],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="MULTI",
            expected_decision=ExpectedDecision.ANSWER,
            abstention_reason=None,
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-009#fe-1",
                    case_id="MH-PILOT-009",
                    fault_class=FaultClass.F5,
                    gold_trigger="proposed_capacity_kw (6.0) > sanctioned_load_kw (4.0)",
                    gold_evidence=["MH-C3-001#cl-6.2"],
                    expected_behavior="Reject 6 kW capacity as exceeding 4 kW sanctioned load",
                ),
                FaultEvent(
                    fault_event_id="MH-PILOT-009#fe-2",
                    case_id="MH-PILOT-009",
                    fault_class=FaultClass.F3,
                    gold_trigger="reliance_on_node('IN-C1-002#cl-2') for post-Feb 2024 application",
                    gold_evidence=["IN-C1-001#cl-4.1", "IN-C1-002#cl-2"],
                    expected_behavior="Apply active PM Surya Ghar 2024 CFA guidelines; reject superseded 2019 formula",
                ),
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-009#nfo-1",
                    case_id="MH-PILOT-009",
                    target_property="jurisdiction",
                    claim_text="MSEDCL is the appropriate distribution licensee for Maharashtra",
                )
            ],
        ),
        # Case 10: F9 Epistemic Abstention (Missing mandatory Sanctioned Load parameter)
        BenchmarkCase(
            case_id="MH-PILOT-010",
            corpus_version=PILOT_CORPUS_VERSION,
            facts=CaseFacts(
                state=StateCode.MH,
                discom=DiscomCode.MSEDCL,
                consumer_category=ConsumerCategory.RESIDENTIAL,
                sanctioned_load_kw=0.0,  # Missing / unreadable
                connected_load_kw=0.0,
                proposed_capacity_kw=4.0,
                premises_type=PremisesType.INDIVIDUAL,
                metering_mode=MeteringMode.NET,
                module_almm_status=AlmmStatus.LISTED,
                dcr_claimed=True,
                subsidy_claimed=True,
                application_stage="technical_feasibility",
                case_date="2024-06-15",
            ),
            inputs=CaseInputs(
                bill="CONSUMER BILL - MSEDCL\nConsumer No: 021548796329\nName: Anjali Deshmukh\nCategory: Residential\nSanctioned Load: [UNREADABLE / TORN / MISSING]\nTariff: LT-I",
                proposal="INSTALLER PROPOSAL\nCapacity: 4.0 kWp Grid-Connected Solar",
                portal_state="MSEDCL RTS PORTAL\nStatus: Pending Bill Verification",
            ),
            applicable_rules=[
                ApplicableRuleReference(
                    rule_id="MH-C3-001#cl-6.2",
                    clause="6.2",
                    effective_date="2019-12-30",
                    jurisdiction="MH",
                    applicability_basis="Clause 6.2 makes sanctioned load a strictly mandatory precondition for capacity feasibility",
                )
            ],
            expected_answer=ExpectedAnswer(
                blocking_stage="Data Verification",
                root_cause="Sanctioned load is unreadable/missing from consumer documentation",
                next_action="Abstain from feasibility determination and request an authenticated electricity bill",
                prohibited_actions=[
                    "Guessing sanctioned load or approving without load documentation"
                ],
                computed=[],
            ),
            ground_truth_provenance=GroundTruthProvenance(
                basis="explicit_applicability", confidence=ConfidenceLevel.HIGH
            ),
            failure_class_probed="F9",
            expected_decision=ExpectedDecision.ABSTAIN,
            abstention_reason="F9: missing mandatory case facts (sanctioned_load_kw is unreadable/missing from consumer bill facsimile)",
            fault_events=[
                FaultEvent(
                    fault_event_id="MH-PILOT-010#fe-1",
                    case_id="MH-PILOT-010",
                    fault_class=FaultClass.F9,
                    gold_trigger="facts.sanctioned_load_kw == 0.0 or bill text missing load",
                    gold_evidence=["MH-C3-001#cl-6.2"],
                    expected_behavior="Abstain from approving or rejecting feasibility; request legible bill document",
                )
            ],
            non_fault_opportunities=[
                NonFaultOpportunity(
                    opportunity_id="MH-PILOT-010#nfo-1",
                    case_id="MH-PILOT-010",
                    target_property="jurisdiction",
                    claim_text="Consumer is located in Maharashtra under MSEDCL supply",
                )
            ],
        ),
    ]

    validate_benchmark_suite(cases)
    return cases
