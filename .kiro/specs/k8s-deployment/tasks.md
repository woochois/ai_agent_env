# Implementation Plan: k8s-deployment

## Overview

AI Agent Ops 플랫폼을 Kubernetes에 배포하기 위한 구현 계획입니다. Dockerfile 멀티스테이지 빌드 최적화, Kustomize base/overlay 구조의 K8s 매니페스트 작성, 의존 서비스(PostgreSQL, Elasticsearch) StatefulSet 배포, HPA 자동 스케일링, 그리고 배포 자동화 스크립트를 단계적으로 구현합니다.

## Tasks

- [x] 1. Docker 이미지 최적화 및 빌드 환경 설정
  - [x] 1.1 Dockerfile을 멀티스테이지 빌드로 개선
    - Stage 1 (builder): `python:3.13-slim` 기반으로 requirements.txt 의존성을 `/install` 경로에 설치
    - Stage 2 (final): `python:3.13-slim` 기반으로 builder에서 설치된 패키지를 복사하고 소스 코드 복사
    - EXPOSE 8000, CMD uvicorn 실행 명령 설정
    - 최종 이미지 크기 500MB 이하 목표
    - _Requirements: 1.1, 1.3, 1.6_

  - [x] 1.2 .dockerignore 파일 생성
    - `.venv`, `.git`, `__pycache__`, `.env`, `.hypothesis`, `.pytest_cache`, `k8s/` 패턴 추가
    - Docker 빌드 컨텍스트에서 불필요한 파일 제외
    - _Requirements: 1.4_

- [x] 2. Kubernetes 기본 인프라 매니페스트 작성 (Kustomize base)
  - [x] 2.1 base 디렉토리 구조 및 Namespace, ResourceQuota, LimitRange 생성
    - `k8s/base/kustomization.yaml` 생성 (resources 목록 정의)
    - `k8s/base/namespacce.yaml` 생성 (`ai-agent-ops` Namespace)
    - `k8s/base/resource-quota.yaml` 생성 (CPU 요청 합계 4코어, 메모리 8Gi, Pod 최대 20개)
    - `k8s/base/limit-range.yaml` 생성 (기본 요청 CPU 100m/메모리 128Mi, 기본 제한 CPU 500m/메모리 512Mi)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 2.2 ConfigMap 및 Secret 템플릿 생성
    - `k8s/base/configmap.yaml` 생성 (LOG_LEVEL=INFO, DEBUG_MODE=false, SESSION_TTL_HOURS=24)
    - `k8s/base/secret.yaml` 생성 (OPENAI_API_KEY, DATABASE_URL, ELASTICSEARCH_URL 필수 키 + ANTHROPIC_API_KEY, GOOGLE_API_KEY 선택 키, base64 인코딩 플레이스홀더)
    - 모든 리소스에 `app: ai-agent-ops` 라벨, namespace: ai-agent-ops 설정
    - _Requirements: 4.1, 4.2, 6.2, 9.1_

  - [x] 2.3 AI Agent App Deployment 매니페스트 작성
    - `k8s/base/deployment.yaml` 생성
    - replicas: 2, strategy: RollingUpdate (maxSurge: 1, maxUnavailable: 0)
    - readinessProbe: HTTP GET /health:8000, initialDelay 10s, period 5s, failureThreshold 3
    - livenessProbe: HTTP GET /health:8000, initialDelay 15s, period 10s, failureThreshold 3
    - resources: requests CPU 250m/Memory 256Mi, limits CPU 1000m/Memory 512Mi
    - envFrom으로 ConfigMap 참조, envFrom으로 Secret 참조
    - 선택적 Secret 키에 optional: true 설정
    - 라벨: app=ai-agent-ops, component=api, version=v1.0.0
    - annotation: deploy-timestamp, app-version
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.3, 4.4, 4.5, 9.1, 9.2_

  - [x] 2.4 AI Agent App Service 및 HPA 매니페스트 작성
    - `k8s/base/service.yaml` 생성 (ClusterIP, port 80 → targetPort 8000, name "http", selector: app=ai-agent-ops, component=api)
    - `k8s/base/hpa.yaml` 생성 (minReplicas: 2, maxReplicas: 10, CPU averageUtilization 70%, scaleDown stabilizationWindowSeconds: 300)
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 3. 의존 서비스 매니페스트 작성 (PostgreSQL, Elasticsearch)
  - [x] 3.1 PostgreSQL StatefulSet, Service, Secret 매니페스트 작성
    - `k8s/base/postgres/statefulset.yaml` 생성 (replicas: 1, PVC 1Gi, reclaimPolicy: Retain)
    - `k8s/base/postgres/service.yaml` 생성 (ClusterIP, port 5432)
    - `k8s/base/postgres/secret.yaml` 생성 (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
    - readinessProbe: TCP 포트 5432 연결 확인
    - 라벨: app=ai-agent-ops, component=database
    - _Requirements: 5.1, 5.3, 5.4, 5.5, 5.6, 6.2_

  - [x] 3.2 Elasticsearch StatefulSet, Service 매니페스트 작성
    - `k8s/base/elasticsearch/statefulset.yaml` 생성 (replicas: 1, PVC 2Gi, reclaimPolicy: Retain, xpack.security.enabled=false)
    - `k8s/base/elasticsearch/service.yaml` 생성 (ClusterIP, port 9200)
    - readinessProbe: HTTP GET /_cluster/health 포트 9200
    - 라벨: app=ai-agent-ops, component=search
    - _Requirements: 5.2, 5.3, 5.5, 5.6, 6.2_

- [ ] 4. Checkpoint - 기본 매니페스트 검증
  - `kubectl apply --dry-run=client -f` 명령으로 모든 base 매니페스트의 스키마 유효성 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Kustomize 환경별 오버레이 구성
  - [x] 5.1 개발(dev) 환경 오버레이 작성
    - `k8s/overlays/dev/kustomization.yaml` 생성 (base 참조, namespace: ai-agent-ops, patches 목록)
    - `k8s/overlays/dev/deployment-patch.yaml` 생성 (replicas: 2, 작은 리소스 할당)
    - `k8s/overlays/dev/service-patch.yaml` 생성 (type: LoadBalancer로 패치)
    - `k8s/overlays/dev/configmap-patch.yaml` 생성 (DEBUG_MODE=true, LOG_LEVEL=DEBUG)
    - _Requirements: 3.3, 8.2_

  - [x] 5.2 운영(prod) 환경 오버레이 작성
    - `k8s/overlays/prod/kustomization.yaml` 생성 (base 참조, namespace: ai-agent-ops, patches 목록)
    - `k8s/overlays/prod/deployment-patch.yaml` 생성 (replicas: 3, 큰 리소스 할당)
    - `k8s/overlays/prod/configmap-patch.yaml` 생성 (LOG_LEVEL=WARNING)
    - _Requirements: 8.2_

  - [x] 5.3 Kustomize 빌드 검증
    - `kustomize build k8s/overlays/dev` 및 `kustomize build k8s/overlays/prod` 실행하여 렌더링 정합성 확인
    - base에 정의된 모든 리소스가 각 환경 출력에 포함되는지 확인
    - _Requirements: 8.2_

- [x] 6. 배포 자동화 스크립트 작성
  - [x] 6.1 deploy.sh 스크립트 구현
    - `k8s/scripts/deploy.sh` 생성
    - 환경 인자 파싱 (dev/prod, 잘못된 인자 시 사용법 출력 후 종료)
    - kubectl 클러스터 연결 확인 (실패 시 에러 메시지 출력 후 종료)
    - Kustomize로 환경별 매니페스트 렌더링 및 순차 적용
    - 배포 순서: Namespace → ResourceQuota/LimitRange → ConfigMap/Secret → PostgreSQL → Elasticsearch → App Deployment/Service/HPA
    - 각 단계 Ready 대기 (timeout 300초, 실패 시 stderr로 에러 출력)
    - 각 단계 진행 상태를 stdout으로 출력
    - 실행 권한 부여 (`chmod +x`)
    - _Requirements: 8.1, 8.3, 8.4, 8.5_

- [ ] 7. 모니터링 및 로깅 지원 설정
  - [x] 7.1 metrics-server 배포 매니페스트 또는 설치 방법 문서화
    - Docker Desktop Kubernetes 환경에서 metrics-server 설치 방법을 deploy.sh에 포함하거나 별도 가이드 작성
    - HPA 동작을 위한 metrics-server 필수 사전 조건 반영
    - _Requirements: 9.4_

  - [ ] 7.2 k9s 모니터링 지원을 위한 라벨/어노테이션 일관성 검증
    - 모든 매니페스트에 app, component, version 라벨이 올바르게 부여되었는지 확인
    - Pod annotation에 deploy-timestamp, app-version이 포함되어 있는지 확인
    - k9s에서 라벨 기반 필터링 가능한 구조인지 최종 검증
    - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [ ] 8. base kustomization.yaml에 모든 리소스 등록 및 통합 확인
  - [ ] 8.1 kustomization.yaml 리소스 목록 완성 및 전체 dry-run 검증
    - `k8s/base/kustomization.yaml`의 resources 목록에 모든 매니페스트 파일 등록
    - `kubectl apply --dry-run=client -k k8s/overlays/dev` 실행하여 전체 통합 검증
    - 라벨-셀렉터 일치성, 환경 변수 참조 무결성, 네임스페이스 격리 확인
    - _Requirements: 2.6, 3.1, 4.1, 4.2, 6.1, 6.2_

- [ ] 9. Final checkpoint - 전체 배포 검증
  - `kustomize build` 및 `kubectl --dry-run=client` 최종 검증
  - deploy.sh 스크립트 실행 가능 여부 확인
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- 이 기능은 Infrastructure as Code로 PBT(Property-Based Testing)가 적합하지 않으므로, `kubectl --dry-run=client` 및 `kustomize build`를 통한 정적 검증을 사용합니다
- 각 태스크는 이전 태스크의 결과물에 의존하므로 순서대로 진행합니다
- Secret 값은 플레이스홀더로 제공되며, 실제 값은 배포 시 사용자가 수동으로 설정합니다
- Docker Desktop Kubernetes 환경을 대상으로 하며, metrics-server가 별도 설치 필요할 수 있습니다
- Checkpoints에서 `kubectl apply --dry-run=client`를 활용하여 매니페스트 유효성을 검증합니다

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["3.1", "3.2"] },
    { "id": 4, "tasks": ["5.1", "5.2"] },
    { "id": 5, "tasks": ["5.3", "6.1"] },
    { "id": 6, "tasks": ["7.1", "7.2", "8.1"] }
  ]
}
```
