from typing import Any, Dict, List, Optional, Sequence, Tuple

from security.field_access import (
    allowed_labels_for_role,
    normalize_sensitivity,
    normalize_user_role,
)


def _normalize_role_sequence(values: Any, policy: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        role = normalize_user_role(value, policy)
        if role and role not in seen:
            out.append(role)
            seen.add(role)
    return out


def _relation_specs(policy: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    specs: Dict[str, Dict[str, Any]] = {}
    raw = policy.get("relations") or {}
    for relation_type, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        metadata_key = str(spec.get("metadata_key") or spec.get("id_field") or "").strip()
        source_type = str(spec.get("source_type") or "").strip().lower()
        target_type = str(spec.get("target_type") or "").strip().lower()
        if not relation_type or not metadata_key or not source_type or not target_type:
            continue
        specs[str(relation_type)] = {
            "relation_type": str(relation_type),
            "source_type": source_type,
            "target_type": target_type,
            "metadata_key": metadata_key,
            "field_name": str(spec.get("field_name") or metadata_key),
            "edge_sensitivity": normalize_sensitivity(
                spec.get("edge_sensitivity") or spec.get("sensitivity") or "protected",
                policy,
            ),
            "disclose_roles": _normalize_role_sequence(spec.get("disclose_roles"), policy),
            "traverse_roles": _normalize_role_sequence(spec.get("traverse_roles"), policy),
        }
    return specs


def _metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    return item.get("metadata", {}) if isinstance(item, dict) else {}


def _doc_type(item: Dict[str, Any]) -> str:
    meta = _metadata(item)
    return str(meta.get("doc_type") or "document").strip().lower()


def _entity_id(item: Dict[str, Any]) -> str:
    meta = _metadata(item)
    if meta.get("entity_id"):
        return str(meta["entity_id"])
    doc_type = _doc_type(item)
    if doc_type == "product" and meta.get("rezept_id"):
        return f"product:{meta['rezept_id']}"
    if doc_type == "formulation" and meta.get("rezeptur_id"):
        return f"formulation:{meta['rezeptur_id']}"
    if doc_type == "process" and meta.get("verfahren_id"):
        return f"process:{meta['verfahren_id']}"
    return str(meta.get("document_id") or "unknown")


def relation_edges_for_entity(item: Dict[str, Any], policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = _metadata(item)
    source_type = _doc_type(item)
    source_entity = _entity_id(item)
    edges: List[Dict[str, Any]] = []
    for _, spec in _relation_specs(policy).items():
        if spec["source_type"] != source_type:
            continue
        value = meta.get(spec["metadata_key"])
        if value in (None, ""):
            continue
        value_text = str(value).strip()
        if not value_text:
            continue
        edge = dict(spec)
        edge.update({
            "source_entity": source_entity,
            "target_entity": f"{spec['target_type']}:{value_text}",
            "value": value_text,
            "sensitivity": spec["edge_sensitivity"],
        })
        edges.append(edge)
    return edges


def relation_visibility_for_role(
    edge: Dict[str, Any],
    user_role: str,
    policy: Dict[str, Any],
    action: str = "disclose",
) -> Tuple[bool, str]:
    role = normalize_user_role(user_role, policy)
    roles_key = "traverse_roles" if action == "traverse" else "disclose_roles"
    explicit_roles = _normalize_role_sequence(edge.get(roles_key), policy)
    if explicit_roles:
        if role in explicit_roles:
            return True, f"allowed by relation-specific {roles_key}"
        return False, f"role '{role}' is not listed in relation-specific {roles_key}"

    sensitivity = normalize_sensitivity(edge.get("sensitivity") or edge.get("edge_sensitivity"), policy)
    allowed = allowed_labels_for_role(role, policy)
    if sensitivity in allowed:
        return True, "allowed by role label policy"
    return False, f"edge sensitivity '{sensitivity}' is not permitted for role '{role}'"


def relation_allowed_for_role(
    edge: Dict[str, Any],
    user_role: str,
    policy: Dict[str, Any],
    action: str = "disclose",
) -> bool:
    allowed, _ = relation_visibility_for_role(edge, user_role, policy, action=action)
    return allowed


def matching_relation_edge(
    item: Dict[str, Any],
    policy: Dict[str, Any],
    metadata_key: str,
    target_type: Optional[str] = None,
    value: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    for edge in relation_edges_for_entity(item, policy):
        if edge.get("metadata_key") != metadata_key:
            continue
        if target_type and edge.get("target_type") != target_type:
            continue
        if value is not None and str(edge.get("value")) != str(value):
            continue
        return edge
    return None


def project_relation_edges_for_user(
    item: Dict[str, Any],
    user_role: str,
    policy: Dict[str, Any],
    enforce_access: bool = True,
) -> Dict[str, Any]:
    visible_fields: List[str] = []
    removed_fields: List[str] = []
    removed_reasons: Dict[str, str] = {}
    rendered_lines: List[str] = []
    restricted_values: List[Dict[str, Any]] = []
    role = normalize_user_role(user_role, policy)
    for edge in relation_edges_for_entity(item, policy):
        field_name = f"relation:{edge['relation_type']}"
        disclose_allowed, disclose_reason = relation_visibility_for_role(
            edge, role, policy, action="disclose"
        )
        traverse_allowed, _ = relation_visibility_for_role(edge, role, policy, action="traverse")
        if not enforce_access:
            disclose_allowed = True
            traverse_allowed = True
            disclose_reason = "relation access guard disabled"
        if disclose_allowed:
            visible_fields.append(field_name)
            traversal = "traversal_allowed" if traverse_allowed else "traversal_denied"
            rendered_lines.append(
                f"- {field_name}: {edge['source_entity']} -> {edge['target_entity']} "
                f"({edge['metadata_key']}: {edge['value']}; {traversal})"
            )
        else:
            removed_fields.append(field_name)
            removed_reasons[field_name] = disclose_reason
            restricted_values.append({
                "field_name": field_name,
                "value": edge["value"],
                "relation_type": edge["relation_type"],
                "target_entity": edge["target_entity"],
                "sensitivity": edge["sensitivity"],
            })
    return {
        "visible_fields": visible_fields,
        "removed_fields": removed_fields,
        "removed_reasons": removed_reasons,
        "rendered_lines": rendered_lines,
        "restricted_values": restricted_values,
    }


def render_relation_eval_lines(
    item: Dict[str, Any],
    user_role: str,
    policy: Dict[str, Any],
    enforce_access: bool = True,
) -> List[str]:
    role = normalize_user_role(user_role, policy)
    lines: List[str] = []
    for edge in relation_edges_for_entity(item, policy):
        disclose_allowed, _ = relation_visibility_for_role(edge, role, policy, action="disclose")
        traverse_allowed, _ = relation_visibility_for_role(edge, role, policy, action="traverse")
        if not enforce_access:
            disclose_allowed = True
            traverse_allowed = True
        visibility = "allowed" if disclose_allowed else "restricted_for_role"
        disclosure_rule = f"may_disclose_to_{role}" if disclose_allowed else f"do_not_disclose_to_{role}"
        traversal_rule = f"may_traverse_for_{role}" if traverse_allowed else f"do_not_traverse_for_{role}"
        lines.append(
            f"- relation:{edge['relation_type']} "
            f"[edge_sensitivity={edge['sensitivity']}; visibility={visibility}; "
            f"disclosure_rule={disclosure_rule}; traversal_rule={traversal_rule}; "
            f"source_type={edge['source_type']}; target_type={edge['target_type']}]: "
            f"{edge['source_entity']} -> {edge['target_entity']} "
            f"via {edge['metadata_key']}={edge['value']}"
        )
    return lines


def collect_relation_fields_by_visibility(
    results: Sequence[Dict[str, Any]],
    user_role: str,
    policy: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    role = normalize_user_role(user_role, policy)
    fields_by_visibility: Dict[str, List[Dict[str, Any]]] = {"allowed": [], "restricted": []}
    for item in results:
        for edge in relation_edges_for_entity(item, policy):
            visible, _ = relation_visibility_for_role(edge, role, policy, action="disclose")
            key = "allowed" if visible else "restricted"
            fields_by_visibility[key].append({
                "field_name": f"relation:{edge['relation_type']}",
                "value": edge["value"],
                "sensitivity": edge["sensitivity"],
                "entity_id": edge["source_entity"],
                "doc_type": edge["source_type"],
                "relation_type": edge["relation_type"],
                "target_entity": edge["target_entity"],
            })
    return fields_by_visibility


def id_key_allowed_for_role(metadata_key: str, user_role: str, policy: Dict[str, Any]) -> bool:
    if metadata_key == "rezept_id":
        return True
    role = normalize_user_role(user_role, policy)
    sensitivity = normalize_sensitivity("protected", policy)
    return sensitivity in allowed_labels_for_role(role, policy)
