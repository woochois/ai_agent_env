# metrics-server 설치 가이드 (Docker Desktop Kubernetes)

이 문서는 AI Agent Ops 플랫폼의 **HPA(Horizontal Pod Autoscaler)** 동작과
**k9s에서의 Pod별 CPU/메모리 사용량 조회**(Requirement 9.4)를 위해 필요한
`metrics-server` 설치 방법을 설명합니다.

## 왜 필요한가 (사전 조건)

- HPA(`k8s/base/hpa.yaml`)는 Pod의 평균 CPU 사용률(70% 임계값)을 기준으로
  replica 수를 자동 조절합니다. 이 CPU 사용률 지표는 **metrics-server가
  Metrics API(`metrics.k8s.io`)를 제공해야만** 수집됩니다.
- metrics-server가 없으면 HPA는 `TARGETS`에 `<unknown>`을 표시하고
  스케일링 결정을 내리지 못합니다.
- k9s의 Pod/노드 CPU·메모리 사용량 컬럼도 metrics-server에 의존합니다.

> 요약: **metrics-server는 HPA와 k9s 메트릭 조회의 필수 사전 조건입니다.**
> 애플리케이션 배포(`deploy.sh`) 자체는 metrics-server 없이도 성공하지만,
> 자동 스케일링은 metrics-server 설치 후에만 동작합니다.

## 설치 여부 확인

```bash
# metrics-server 배포 존재 여부
kubectl get deployment metrics-server -n kube-system

# Metrics API 등록 여부
kubectl get apiservice v1beta1.metrics.k8s.io

# Pod 메트릭이 수집되는지 확인 (설치 후 30~60초 대기 필요)
kubectl top pods -n ai-agent-ops
```

`kubectl top` 명령이 값을 반환하면 정상 동작 중입니다.

## 설치 방법

### 1. 공식 components.yaml 적용

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### 2. Docker Desktop 전용: `--kubelet-insecure-tls` 패치

Docker Desktop의 Kubernetes 노드는 kubelet이 사용하는 serving 인증서가
metrics-server의 기본 TLS 검증을 통과하지 못합니다. 이 때문에
metrics-server Pod가 `x509: cannot validate certificate` 오류로
`Ready` 상태가 되지 못합니다.

로컬 개발 환경에서는 다음 패치로 kubelet TLS 검증을 비활성화합니다.

```bash
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

> ⚠️ `--kubelet-insecure-tls`는 **로컬 개발 환경 전용**입니다.
> 운영(prod) 클러스터에서는 적절한 kubelet serving 인증서를 구성하고
> 이 플래그를 사용하지 마세요.

### 3. 롤아웃 완료 대기

```bash
kubectl rollout status deployment/metrics-server -n kube-system --timeout=120s
```

## 제거

```bash
kubectl delete -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

## deploy.sh와의 연동

`k8s/scripts/deploy.sh`는 배포 시작 전에 metrics-server 설치 여부를
**비파괴적으로 점검**합니다.

- 이미 설치되어 있으면: 정상 메시지를 출력하고 진행합니다.
- 설치되어 있지 않으면: HPA가 동작하지 않는다는 **경고**를 출력하지만,
  배포는 계속 진행합니다(앱 배포 자체는 metrics-server에 의존하지 않음).
- 자동 설치를 원하면 환경 변수로 opt-in 할 수 있습니다:

```bash
# metrics-server를 자동 설치(+ Docker Desktop TLS 패치)한 뒤 배포
INSTALL_METRICS_SERVER=true ./k8s/scripts/deploy.sh dev
```

자동 설치는 위 1~3단계(공식 components.yaml 적용 → `--kubelet-insecure-tls`
패치 → 롤아웃 대기)를 그대로 수행합니다.

## 참고

- 공식 저장소: https://github.com/kubernetes-sigs/metrics-server
- HPA 매니페스트: `k8s/base/hpa.yaml`
- 자동 스케일링 요구사항: Requirement 7 (HPA), Requirement 9.4 (메트릭 조회)
