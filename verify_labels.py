import sys, yaml

POD_OWNER_KINDS = {"Deployment", "StatefulSet"}

def check(path, env):
    with open(path) as f:
        docs = [d for d in yaml.safe_load_all(f) if d]
    print(f"\n=== {env} overlay: {len(docs)} resources ===")
    problems = []
    for d in docs:
        kind = d.get("kind")
        meta = d.get("metadata", {})
        name = meta.get("name")
        labels = meta.get("labels", {}) or {}
        # 9.1: app, component, version present; app == ai-agent-ops
        for key in ("app", "component", "version"):
            if key not in labels:
                problems.append(f"[9.1] {kind}/{name} missing label '{key}'")
        if labels.get("app") != "ai-agent-ops":
            problems.append(f"[9.1] {kind}/{name} app label != ai-agent-ops (got {labels.get('app')!r})")
        if labels.get("version") and labels.get("version") != "v1.0.0":
            problems.append(f"[9.1] {kind}/{name} version != v1.0.0 (got {labels.get('version')!r})")
        # 9.2: Pod template annotations on workload kinds
        if kind in POD_OWNER_KINDS:
            tmpl = d.get("spec", {}).get("template", {})
            tmeta = tmpl.get("metadata", {})
            tann = tmeta.get("annotations", {}) or {}
            tlabels = tmeta.get("labels", {}) or {}
            for key in ("app", "component", "version"):
                if key not in tlabels:
                    problems.append(f"[9.1] {kind}/{name} pod template missing label '{key}'")
            for ann in ("deploy-timestamp", "app-version"):
                if ann not in tann:
                    problems.append(f"[9.2] {kind}/{name} pod template missing annotation '{ann}'")
        comp = labels.get("component")
        print(f"  {kind}/{name}: app={labels.get('app')} component={comp} version={labels.get('version')}")
    return problems

allp = []
allp += check("/tmp/dev-rendered.yaml", "dev")
allp += check("/tmp/prod-rendered.yaml", "prod")

print("\n=== RESULT ===")
if allp:
    for p in allp:
        print("FAIL:", p)
    sys.exit(1)
print("All label (9.1) and annotation (9.2) consistency checks PASSED.")
