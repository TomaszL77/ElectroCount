"""Apply a complete analysis atomically; different labels are discoveries, not rejections."""
from dataclasses import asdict
from .domain import Detection, near


class ResultsManager:
    def apply(self, project, group_id, page, result):
        group = next(g for g in project.groups if g.id == group_id)
        updated_template=result.get("template",{})
        if updated_template.get("definition_version",0)>=(group.template or {}).get("definition_version",0) and updated_template.get("representation"):
            group.template={**updated_template,"page":(group.template or {}).get("page",page)}
        if group.template and group.template.get('representation'):
            group.template['group_id']=group.id
            group.template['representation']['group_id']=group.id
        from .text_roles import TextRoleClassifier
        if (group.label and TextRoleClassifier().classify(group.label)[0]!='DEVICE_LABEL' and
                group.name.strip().upper()==group.label.strip().upper() and result.get('label')):
            group.name=result['label']
        if not group.label or TextRoleClassifier().classify(group.label)[0]!='DEVICE_LABEL':
            group.label = result["label"]
        previous = [d for d in project.detections if d.page == page and d.source == "automatic"
                    and (d.group == group_id or (not d.group and d.requested_group == group_id))]
        untouched = [d for d in project.detections if d not in previous]
        previous_discoveries = [d for d in project.discoveries if d["requested_group"] == group_id and d["page"] == page]
        discoveries = [d for d in project.discoveries if not (d["requested_group"] == group_id and d["page"] == page)]
        used = set()
        new = []
        for kind in ("matches", "review", "discovered_other_label"):
            for hit in result[kind]:
                old = next((d for d in previous if d.id not in used and near(d.rect, hit["rect"])), None)
                if old:
                    used.add(old.id)
                if kind == "discovered_other_label":
                    prior = next((d for d in previous_discoveries if near(d["rect"], hit["rect"])), {})
                    discoveries.append({**hit, "page": page, "requested_group": group_id,
                                        "previous_detection": asdict(old) if old else prior.get("previous_detection")})
                    continue
                d = Detection(group_id if kind == "matches" else "", page, hit["rect"],
                              score=hit["graphic_score"], requested_group=group_id,
                              **{k: hit[k] for k in ("label", "label_bbox", "graphic_score", "text_score",
                                  "spatial_association_score", "confidence", "reason")})
                for key in ("template_score","feature_score","geometry_score","verification_method","verification_details","candidate_source","signals"):
                    if key in hit:
                        setattr(d,key,hit[key])
                if old:
                    d.id = old.id
                    d.previous_decision = old.previous_decision
                    if kind == "matches" and (not old.label or old.label == hit["label"]):
                        d.decision = old.decision
                    elif old.decision == "rejected":
                        d.decision = "rejected"
                    else:
                        d.previous_decision = old.decision
                new.append(d)
        # Do not silently keep old automatic quantities which the new analysis cannot confirm.
        for old in previous:
            if old.id not in used:
                old.previous_decision = old.decision
                if old.decision != "rejected":
                    old.group, old.decision, old.reason = "", "review", "not_rediscovered"
                    old.requested_group = group_id
                new.append(old)
        project.analysis_reports[f"{group_id}:{page}"] = {"diagnostics":result.get("diagnostics",{}),"counts":result.get("counts",{}),"legend_matches":result.get("legend_matches",[]),"result_sha256":result.get("result_sha256"),"pipeline":result.get("pipeline",{}),"stages":result.get("stages",{}),"rejected_candidates":result.get("rejected_candidates",[]),"coverage_warnings":result.get("coverage_warnings",[])}
        project.detections = untouched + new
        project.discoveries = discoveries
        project.text_items[str(page)] = [{**item, "page": page} for item in result["text_items"]]
        return {"matches": len(result["matches"]), "review": len(result["review"]),
                "other": len(result["discovered_other_label"])}
