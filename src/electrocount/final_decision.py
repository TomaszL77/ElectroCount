"""Exact device label resolves variants; image/color cannot override a mismatch."""


class FinalDecisionEngine:
    def decide(self, expected, actual, signals, geometry_verified=True):
        weights={'geometry_score':.25,'feature_score':.15,'visual_ai_score':.20,
                 'color_score':.10,'device_label_score':.25,'spatial_text_score':.05,'text_role_confidence':.05}
        present={k:w for k,w in weights.items() if signals.get(k) is not None}
        confidence=sum(signals[k]*w for k,w in present.items())/max(sum(present.values()),1e-9)
        if not geometry_verified:return 'REJECTED',confidence,'geometry_not_verified'
        if expected and actual and actual!=expected:return 'OTHER_VARIANT',confidence,'different_device_label'
        if expected and not actual:return 'REVIEW',confidence,'missing_or_ambiguous_device_label'
        if signals.get('visual_ai_score') is not None and confidence<.78:
            return 'REVIEW',confidence,'insufficient_combined_evidence'
        return 'MATCH',confidence,'exact_device_label' if expected else 'symbol_geometry_verified'
