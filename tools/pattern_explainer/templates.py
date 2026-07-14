"""Explanation templates for tools.pattern_explainer (stdlib string.Template).

Templates use {placeholder} substitution filled by core.py. Kept as plain
prose chunks so generation is deterministic and auditable.
"""

# ---- Collision cluster ----
COLLISION_ONE_LINER = "Facts {members} ({concept}) form a semantic collision cluster."
COLLISION_SUMMARY = (
    "{size} facts related to {theme} are frequently confused in query routing. "
    "Grains {top_pair_members} collide most often ({top_pair_count} times), "
    "suggesting they are structurally similar in query space. This cluster may "
    "represent a region of high semantic ambiguity."
)
COLLISION_DETAILED = (
    "This collision cluster groups {size} related concepts: {member_list}. "
    "The cluster shows {coherence_label} coherence ({coherence}), indicating these "
    "facts are {coherence_meaning}. Collision density is {density}, meaning the "
    "cluster members collide {density_meaning} with each other.\n\n"
    "The pairwise collision breakdown reveals:\n{pair_lines}\n\n"
    "These facts may be isomorphic in query space\u2014the same query could legitimately "
    "map to any of them. Alternatively, the system may be conflating related-but-distinct "
    "concepts due to insufficient ternary discrimination."
)
COLLISION_PAIR_LINE = "- Facts {a}\u2194{b}: {count} collisions ({rank} pair)"
COLLISION_IMPLICATIONS = [
    "Query ambiguity: users asking about this theme may legitimately want any of these facts.",
    "Grain confusion: the grain routing system treats these facts as interchangeable.",
    "Opportunity: this cluster could benefit from disambiguation rules or refined ternary deltas.",
]
COLLISION_RECOMMENDATIONS = [
    "Review ternary delta values for {members}; are they sufficiently distinct?",
    "Analyze collision queries: do they have common keywords indicating ambiguity?",
    "Consider creating a disambiguation rule that branches on the competing concepts in this theme.",
]

# ---- Anomaly ----
ANOMALY_ONE_LINER_INCREASE = (
    "{entity} experienced a sudden spike in false positive rate ({magnitude} baseline)."
)
ANOMALY_ONE_LINER_DECREASE = (
    "{entity} experienced a sudden drop in false positive rate ({magnitude} baseline)."
)
ANOMALY_ONE_LINER_GENERIC = (
    "{entity} showed a {type_label} anomaly (severity {severity_label})."
)
ANOMALY_SUMMARY = (
    "{entity}'s false positive rate jumped from {baseline_pct} (historical baseline) to "
    "{observed_pct} in the {window_short}. This {magnitude}x increase is substantial and falls "
    "outside normal variation{full_dev}. The grain is now misrouting {observed_pct} of queries."
)
ANOMALY_DETAILED = (
    "Over the {window_short} ({window}), {entity} showed a sharp increase in false positives\u2014"
    "cases where the grain confidently returned an incorrect result.\n\n"
    "Metrics:\n"
    "- Historical baseline: {baseline_pct} false positive rate (over last 7 days)\n"
    "- Observed rate: {observed_pct} (in the {window_short})\n"
    "- Deviation: {magnitude}x the baseline{full_dev}\n\n"
    "This shift is sudden and severe. It suggests a systematic change in either:\n"
    "1. Query patterns (users asking different types of questions), or\n"
    "2. Grain behavior (ternary deltas or search weights shifted), or\n"
    "3. Knowledge base (new facts added that confuse the routing logic)\n\n"
    "{collision_note}"
)
ANOMALY_TYPE_EXPLANATION = (
    "Sudden increases in false positive rates indicate a routing component has lost its ability "
    "to distinguish between similar queries. This usually signals either a configuration change, "
    "a shift in query distribution, or drift in the knowledge base."
)
ANOMALY_IMPLICATIONS = [
    "User impact: {observed_pct} of queries routed to this grain are returning incorrect results.",
    "Cascading effects: downstream facts will receive incorrect context.",
    "Signal in Dream Bucket: false positives are recorded; the system is aware of the problem.",
]
ANOMALY_RECOMMENDATIONS = [
    "Immediate: monitor this grain's FP rate; if it continues above 20%, consider deprioritizing the grain temporarily.",
    "Investigation: compare query logs (recent window) to baseline; look for keyword/pattern shifts.",
    "Investigation: review recent changes to grain config (weights, ternary deltas, search parameters).",
    "Investigation: check if any new facts were added that might confuse the routing logic.",
    "Hypothesis: the grain and its frequent collision partners may need stronger ternary discrimination.",
]

# ---- Pattern reliability ----
PATTERN_ONE_LINER = "Pattern {sequence} is {reliability_label} (F1: {f1})."
PATTERN_SUMMARY = (
    "This tool sequence appears in {frequency} successful reasoning chains. When it fires, it "
    "succeeds {precision} of the time (precision). It catches {recall} of correct outcomes (recall). "
    "Overall reliability: {reliability_label}."
)
PATTERN_DETAILED = (
    "Pattern {pattern_id} represents a {size}-step tool sequence: {sequence}. This sequence is a "
    "component of the text processing pipeline.\n\n"
    "Reliability metrics:\n"
    "- Precision: {precision} ({precision_rationale})\n"
    "- Recall: {recall} ({recall_rationale})\n"
    "- F1 Score: {f1} ({f1_rationale})\n"
    "- Support: {support} observations ({support_rationale})\n\n"
    "What this means:\n"
    "- When this sequence fires, you can trust the result (high precision).\n"
    "- This sequence covers most of the successful reasoning path (good recall).\n"
    "- The pattern is common and well-understood ({support} occurrences).\n"
    "- {flag_note}"
)
PATTERN_USE_CASES_HIGH = [
    "High confidence: use this pattern for real-time reasoning (precision is high).",
    "Acceptable coverage: pattern covers most success cases (good but not exhaustive).",
    "Learning target: this pattern is a good candidate for procedural edge extraction (stable and reliable).",
]
PATTERN_USE_CASES_MED = [
    "Medium confidence: use with monitoring; collect more observations before trusting fully.",
    "Targeted coverage: pattern covers some success cases; pair with alternatives.",
    "Learning candidate: this pattern may qualify for extraction once sample size grows.",
]
PATTERN_USE_CASES_LOW = [
    "Low confidence: do not rely on this pattern for real-time reasoning yet.",
    "Investigate: determine whether the failure mode is data scarcity or a genuine weak chain.",
    "Collect data: more observations needed before drawing conclusions.",
]

# ---- Multiple patterns aggregate ----
AGGREGATE_SUMMARY = (
    "Of {total} discovered patterns, {high} are highly reliable (F1>0.70), {medium} are medium "
    "confidence, and {low} need investigation. The pattern set is dominated by high-confidence "
    "sequences, suggesting the system has learned stable reasoning chains."
)
AGGREGATE_SUMMARY_MIXED = (
    "Of {total} discovered patterns, {high} are highly reliable (F1>0.70), {medium} are medium "
    "confidence, and {low} need investigation. The pattern set is mixed; several chains still "
    "require more data or tuning."
)
