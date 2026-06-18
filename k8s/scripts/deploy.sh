#!/usr/bin/env bash
#
# deploy.sh — AI Agent Ops Kubernetes 배포 자동화 스크립트
#
# 사용법:
#   ./k8s/scripts/deploy.sh <env>      # env: dev | prod
#
# 동작 개요 (Requirement 8.1, 8.3, 8.4, 8.5):
#   1. 환경 인자(dev/prod) 파싱 — 잘못된 인자 시 사용법 출력 후 종료
#   2. kubectl 클러스터 연결 확인 — 실패 시 에러 출력 후 배포 미시작
#   3. Kustomize로 환경별 매니페스트를 렌더링하여 단계별로 순차 적용
#        Namespace
#        → ResourceQuota / LimitRange
#        → ConfigMap / Secret
#        → PostgreSQL (StatefulSet/Service)
#        → Elasticsearch (StatefulSet/Service)
#        → App (Deployment/Service/HPA)
#   4. 각 단계의 리소스가 Ready 상태가 될 때까지 대기 (timeout 300초)
#   5. 진행 상태는 stdout, 에러는 stderr로 출력
#      (실패해도 이미 완료된 이전 단계는 롤백하지 않고 유지)

set -euo pipefail

# ----------------------------------------------------------------------------
# 상수
# ----------------------------------------------------------------------------
readonly NAMESPACE="ai-agent-ops"
readonly READY_TIMEOUT="300s"
readonly CLUSTER_TIMEOUT="15s"

# metrics-server (HPA 및 k9s 메트릭 조회의 필수 사전 조건 — Requirement 9.4)
#   - 자동 설치는 INSTALL_METRICS_SERVER=true 로 opt-in (기본값: 점검만 수행)
#   - Docker Desktop Kubernetes에서는 kubelet TLS 검증 비활성화 패치가 필요
readonly METRICS_SERVER_MANIFEST="https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"
readonly METRICS_SERVER_GUIDE="k8s/scripts/metrics-server.md"
INSTALL_METRICS_SERVER="${INSTALL_METRICS_SERVER:-false}"

# 스크립트 위치 기준으로 k8s 디렉토리 경로 계산 (호출 위치에 무관하게 동작)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
K8S_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly K8S_DIR

# 렌더링 결과를 담을 임시 파일 (스크립트 종료 시 정리)
RENDERED=""

# ----------------------------------------------------------------------------
# 유틸리티
# ----------------------------------------------------------------------------

# 정보성 메시지 -> stdout
log()  { printf '%s %s\n' "[deploy]" "$*"; }

# 에러 메시지 -> stderr
err()  { printf '%s %s\n' "[deploy][ERROR]" "$*" >&2; }

# 에러 출력 후 종료
die()  { err "$*"; exit 1; }

usage() {
  cat >&2 <<'EOF'
사용법: deploy.sh <env>

인자:
  env    배포 대상 환경. dev 또는 prod 중 하나여야 합니다.

예시:
  ./k8s/scripts/deploy.sh dev
  ./k8s/scripts/deploy.sh prod
EOF
}

# 종료 시 임시 파일 정리
cleanup() {
  if [[ -n "${RENDERED}" && -f "${RENDERED}" ]]; then
    rm -f "${RENDERED}"
  fi
}
trap cleanup EXIT

# ----------------------------------------------------------------------------
# 1. 환경 인자 파싱
# ----------------------------------------------------------------------------
parse_args() {
  if [[ $# -ne 1 ]]; then
    err "환경 인자가 정확히 하나 필요합니다 (받은 인자 수: $#)."
    usage
    exit 1
  fi

  case "$1" in
    dev|prod)
      ENV="$1"
      ;;
    *)
      err "유효하지 않은 환경 인자입니다: '$1'. 'dev' 또는 'prod'만 허용됩니다."
      usage
      exit 1
      ;;
  esac
  readonly ENV

  OVERLAY_DIR="${K8S_DIR}/overlays/${ENV}"
  readonly OVERLAY_DIR

  if [[ ! -d "${OVERLAY_DIR}" ]]; then
    die "오버레이 디렉토리를 찾을 수 없습니다: ${OVERLAY_DIR}"
  fi
}

# ----------------------------------------------------------------------------
# 사전 점검: 필수 CLI 도구 확인
# ----------------------------------------------------------------------------
check_prerequisites() {
  if ! command -v kubectl >/dev/null 2>&1; then
    die "kubectl 명령을 찾을 수 없습니다. kubectl을 설치한 후 다시 시도하세요."
  fi
}

# Kustomize 렌더링 명령 선택:
#   - 독립 kustomize 바이너리가 있으면 사용
#   - 없으면 kubectl 내장 kustomize 사용 (kubectl kustomize)
render_manifests() {
  RENDERED="$(mktemp -t ai-agent-ops-deploy.XXXXXX.yaml)"

  log "Kustomize로 '${ENV}' 환경 매니페스트를 렌더링합니다..."
  if command -v kustomize >/dev/null 2>&1; then
    if ! kustomize build "${OVERLAY_DIR}" >"${RENDERED}"; then
      die "Kustomize 렌더링에 실패했습니다 (kustomize build ${OVERLAY_DIR})."
    fi
  else
    if ! kubectl kustomize "${OVERLAY_DIR}" >"${RENDERED}"; then
      die "Kustomize 렌더링에 실패했습니다 (kubectl kustomize ${OVERLAY_DIR})."
    fi
  fi

  if [[ ! -s "${RENDERED}" ]]; then
    die "렌더링된 매니페스트가 비어 있습니다: ${OVERLAY_DIR}"
  fi
  log "매니페스트 렌더링 완료."
}

# ----------------------------------------------------------------------------
# 2. kubectl 클러스터 연결 확인 (Requirement 8.4)
# ----------------------------------------------------------------------------
check_cluster_connection() {
  log "Kubernetes 클러스터 연결을 확인합니다..."
  if ! kubectl cluster-info --request-timeout="${CLUSTER_TIMEOUT}" >/dev/null 2>&1; then
    err "Kubernetes 클러스터에 연결할 수 없습니다."
    err "kubeconfig 컨텍스트와 클러스터 상태를 확인한 후 다시 시도하세요."
    exit 1
  fi
  log "클러스터 연결 확인 완료."
}

# ----------------------------------------------------------------------------
# metrics-server 사전 점검 / 선택적 설치 (Requirement 9.4)
#
# metrics-server는 HPA의 CPU 사용률 기반 스케일링과 k9s의 Pod CPU/메모리
# 사용량 조회에 필요한 필수 사전 조건입니다. 앱 배포 자체는 metrics-server에
# 의존하지 않으므로, 미설치 상태여도 배포를 중단하지 않고 경고만 출력합니다.
#
#   - 이미 설치됨        : 정상 메시지 출력 후 진행
#   - 미설치 + opt-in    : INSTALL_METRICS_SERVER=true 이면 자동 설치(+TLS 패치)
#   - 미설치 + 기본값    : 경고 출력 후 진행 (HPA 미동작 안내)
# ----------------------------------------------------------------------------
metrics_server_installed() {
  kubectl get deployment metrics-server -n kube-system >/dev/null 2>&1
}

install_metrics_server() {
  log "metrics-server를 설치합니다 (공식 components.yaml 적용)..."
  if ! kubectl apply -f "${METRICS_SERVER_MANIFEST}"; then
    err "metrics-server 설치에 실패했습니다. 수동 설치는 ${METRICS_SERVER_GUIDE}를 참고하세요."
    err "metrics-server 없이 배포를 계속 진행합니다 (HPA는 동작하지 않습니다)."
    return 0
  fi

  # Docker Desktop Kubernetes: kubelet serving 인증서 검증을 통과하지 못하므로
  # 로컬 개발 환경에서는 --kubelet-insecure-tls 패치가 필요합니다.
  log "Docker Desktop 환경용 --kubelet-insecure-tls 패치를 적용합니다..."
  if ! kubectl patch deployment metrics-server -n kube-system --type='json' \
        -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'; then
    err "metrics-server TLS 패치에 실패했습니다. ${METRICS_SERVER_GUIDE}를 참고하여 수동으로 확인하세요."
  fi

  log "metrics-server 롤아웃을 기다립니다 (timeout ${READY_TIMEOUT})..."
  if ! kubectl rollout status deployment/metrics-server -n kube-system --timeout="${READY_TIMEOUT}"; then
    err "metrics-server가 Ready 상태에 도달하지 못했습니다. ${METRICS_SERVER_GUIDE}를 참고하세요."
    err "metrics-server 없이 배포를 계속 진행합니다 (HPA는 동작하지 않습니다)."
    return 0
  fi
  log "metrics-server 설치 완료."
}

check_metrics_server() {
  log "metrics-server(HPA/메트릭 사전 조건) 설치 여부를 확인합니다..."

  if metrics_server_installed; then
    log "metrics-server가 이미 설치되어 있습니다. HPA 및 k9s 메트릭 조회가 가능합니다."
    return 0
  fi

  if [[ "${INSTALL_METRICS_SERVER}" == "true" ]]; then
    log "metrics-server가 설치되어 있지 않아 자동 설치를 진행합니다 (INSTALL_METRICS_SERVER=true)."
    install_metrics_server
    return 0
  fi

  # 미설치 + 자동 설치 비활성: 배포는 계속하되 경고를 남긴다.
  err "metrics-server가 설치되어 있지 않습니다."
  err "HPA의 CPU 기반 자동 스케일링과 k9s의 Pod CPU/메모리 조회가 동작하지 않습니다."
  err "설치 방법은 ${METRICS_SERVER_GUIDE}를 참고하거나, 다음과 같이 자동 설치할 수 있습니다:"
  err "  INSTALL_METRICS_SERVER=true ./k8s/scripts/deploy.sh ${ENV}"
  log "metrics-server 없이 배포를 계속 진행합니다."
}

# ----------------------------------------------------------------------------
# 문서 필터링 유틸리티
#
# 렌더링된 멀티 도큐먼트 YAML(stdin)에서 정규식 패턴과 일치하는 문서만 출력합니다.
# 문서는 '---' 구분자로 나뉩니다.
# ----------------------------------------------------------------------------
select_docs() {
  local pattern="$1"
  awk -v pat="${pattern}" '
    BEGIN { RS = "\n---\n"; ORS = "" }
    {
      doc = $0
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", doc)
      if (doc != "" && doc ~ pat) {
        print "---\n" doc "\n"
      }
    }
  ' "${RENDERED}"
}

# 패턴과 일치하는 문서를 적용한다.
#   $1 = 사람이 읽을 단계 설명
#   $2 = 일치시킬 정규식 패턴
apply_stage() {
  local description="$1"
  local pattern="$2"
  local docs

  docs="$(select_docs "${pattern}")"
  if [[ -z "${docs}" ]]; then
    err "단계 '${description}'에 적용할 리소스를 찾지 못했습니다 (패턴: ${pattern})."
    exit 1
  fi

  log "[적용] ${description}"
  if ! printf '%s' "${docs}" | kubectl apply -f - ; then
    err "단계 '${description}' 적용에 실패했습니다."
    err "이미 완료된 이전 단계의 리소스는 유지됩니다."
    exit 1
  fi
}

# 워크로드(StatefulSet/Deployment)가 Ready 상태가 될 때까지 대기한다.
#   $1 = 사람이 읽을 단계 설명
#   $2 = 리소스 종류 (deployment | statefulset)
#   $3 = 리소스 이름
wait_ready() {
  local description="$1"
  local kind="$2"
  local name="$3"

  log "[대기] ${description} — '${kind}/${name}'가 Ready 상태가 될 때까지 (timeout ${READY_TIMEOUT})"
  if ! kubectl rollout status "${kind}/${name}" \
        --namespace "${NAMESPACE}" \
        --timeout="${READY_TIMEOUT}"; then
    err "단계 '${description}'의 '${kind}/${name}'가 ${READY_TIMEOUT} 이내에 Ready 상태에 도달하지 못했습니다."
    err "이미 완료된 이전 단계의 리소스는 유지됩니다."
    exit 1
  fi
  log "[완료] ${description}"
}

# ----------------------------------------------------------------------------
# 3~4. 순차 배포 + Ready 대기
# ----------------------------------------------------------------------------
deploy() {
  log "==> '${ENV}' 환경 배포를 시작합니다 (namespace: ${NAMESPACE})."

  # 1단계: Namespace
  apply_stage "1/6 Namespace" '(^|\n)kind: Namespace($|\n)'

  # 2단계: ResourceQuota / LimitRange
  apply_stage "2/6 ResourceQuota / LimitRange" '(^|\n)kind: (ResourceQuota|LimitRange)($|\n)'

  # 3단계: ConfigMap / Secret (앱 + 의존 서비스의 모든 ConfigMap/Secret)
  apply_stage "3/6 ConfigMap / Secret" '(^|\n)kind: (ConfigMap|Secret)($|\n)'

  # 4단계: PostgreSQL (StorageClass/StatefulSet/Service — component: database)
  apply_stage "4/6 PostgreSQL" 'component: database'
  wait_ready "4/6 PostgreSQL" statefulset postgres

  # 5단계: Elasticsearch (StorageClass/StatefulSet/Service — component: search)
  apply_stage "5/6 Elasticsearch" 'component: search'
  wait_ready "5/6 Elasticsearch" statefulset elasticsearch

  # 6단계: AI Agent App (Deployment/Service/HPA — component: api)
  apply_stage "6/6 AI Agent App" 'component: api'
  wait_ready "6/6 AI Agent App" deployment ai-agent-app

  log "==> 배포가 성공적으로 완료되었습니다."
  log "리소스 상태 확인: kubectl get all -n ${NAMESPACE}"
}

# ----------------------------------------------------------------------------
# 엔트리포인트
# ----------------------------------------------------------------------------
main() {
  parse_args "$@"
  check_prerequisites
  check_cluster_connection
  check_metrics_server
  render_manifests
  deploy
}

main "$@"
