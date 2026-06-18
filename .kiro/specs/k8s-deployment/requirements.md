# Requirements Document

## Introduction

AI Agent Ops 플랫폼을 Docker 컨테이너로 빌드하고 Kubernetes(k8s) 클러스터에 배포하기 위한 요구사항을 정의합니다. 이 기능은 로컬 Docker Compose 기반 운영에서 Kubernetes 기반 오케스트레이션 환경으로 전환하여, 확장성·가용성·관리 편의성을 확보하고 k9s를 통한 실시간 모니터링 및 관리를 가능하게 합니다.

## Glossary

- **AI_Agent_App**: FastAPI/Uvicorn 기반 AI 에이전트 플랫폼 애플리케이션 컨테이너
- **K8s_Cluster**: Kubernetes 클러스터 (로컬 개발 환경에서는 Docker Desktop 또는 minikube)
- **Deployment_Manifest**: Kubernetes Deployment 리소스를 정의하는 YAML 매니페스트 파일
- **Service_Manifest**: Kubernetes Service 리소스를 정의하는 YAML 매니페스트 파일
- **ConfigMap**: 비민감 환경 설정을 저장하는 Kubernetes ConfigMap 리소스
- **Secret**: 민감 정보(API 키, 비밀번호)를 저장하는 Kubernetes Secret 리소스
- **Health_Probe**: Kubernetes의 liveness/readiness 프로브를 통한 헬스체크 메커니즘
- **Namespace**: Kubernetes 네임스페이스로 리소스를 논리적으로 격리하는 단위
- **HPA**: Horizontal Pod Autoscaler, Pod 수를 자동으로 조절하는 Kubernetes 리소스
- **Kustomize**: Kubernetes 매니페스트를 환경별로 커스터마이징하는 도구
- **k9s**: Kubernetes 클러스터를 터미널 기반 UI로 모니터링·관리하는 CLI 도구

## Requirements

### Requirement 1: Docker 이미지 빌드 및 레지스트리 관리

**User Story:** As a DevOps 엔지니어, I want to Docker 이미지를 빌드하고 태깅하여 Kubernetes에서 사용할 수 있는 상태로 준비하고 싶다, so that 일관된 배포 아티팩트를 관리할 수 있다.

#### Acceptance Criteria

1. WHEN `docker build` 명령이 실행될 때, THE AI_Agent_App SHALL 프로젝트 루트의 Dockerfile을 사용하여 컨테이너 이미지를 빌드한다
2. WHEN 이미지가 빌드될 때, THE AI_Agent_App SHALL 시맨틱 버전 태그(vMAJOR.MINOR.PATCH 형식, 예: v1.0.0)와 latest 태그를 동시에 부여한다
3. THE AI_Agent_App SHALL 멀티스테이지 빌드를 사용하여 최종 이미지 크기를 500MB 이하로 유지한다
4. WHEN 이미지가 빌드될 때, THE AI_Agent_App SHALL .dockerignore 파일을 통해 .venv, .git, __pycache__, .env 파일을 빌드 컨텍스트에서 제외한다
5. IF Dockerfile 빌드 중 의존성 설치 단계에서 에러가 발생할 경우, THEN THE AI_Agent_App SHALL 에러 메시지를 표준 에러로 출력하고 비정상 종료 코드를 반환한다
6. WHEN 이미지가 빌드 완료된 후, THE AI_Agent_App SHALL 해당 이미지로 컨테이너를 실행했을 때 /health 엔드포인트가 HTTP 200 응답을 반환하는 것을 검증할 수 있다

### Requirement 2: Kubernetes Deployment 매니페스트

**User Story:** As a DevOps 엔지니어, I want to Kubernetes Deployment 매니페스트를 작성하여 AI Agent 앱을 클러스터에 배포하고 싶다, so that Pod의 수명주기를 자동으로 관리할 수 있다.

#### Acceptance Criteria

1. THE Deployment_Manifest SHALL AI_Agent_App 컨테이너를 기본 replica 수 2개로 배포한다
2. THE Deployment_Manifest SHALL 리소스 요청(requests)을 CPU 250m, 메모리 256Mi로, 제한(limits)을 CPU 1000m, 메모리 512Mi로 명시한다
3. WHEN Pod가 시작될 때, THE Deployment_Manifest SHALL readinessProbe를 /health 엔드포인트(HTTP GET, 포트 8000)로 구성하며, initialDelaySeconds 10초, periodSeconds 5초, failureThreshold 3회로 설정한다
4. WHEN Pod가 실행 중일 때, THE Deployment_Manifest SHALL livenessProbe를 /health 엔드포인트(HTTP GET, 포트 8000)로 구성하며, initialDelaySeconds 15초, periodSeconds 10초, failureThreshold 3회로 설정한다
5. THE Deployment_Manifest SHALL RollingUpdate 전략을 maxSurge 1, maxUnavailable 0으로 설정하여 무중단 배포를 보장한다
6. THE Deployment_Manifest SHALL ConfigMap에서 비민감 환경 변수(LOG_LEVEL, DEBUG_MODE, SESSION_TTL_HOURS)를, Secret에서 민감 환경 변수(OPENAI_API_KEY, DATABASE_URL, ELASTICSEARCH_URL)를 주입한다
7. IF readinessProbe가 연속 3회 실패할 경우, THEN THE Deployment_Manifest SHALL 해당 Pod를 Service 엔드포인트에서 제거하여 트래픽을 수신하지 않도록 한다
8. IF livenessProbe가 연속 3회 실패할 경우, THEN THE Deployment_Manifest SHALL 해당 Pod를 재시작한다

### Requirement 3: Kubernetes Service 매니페스트

**User Story:** As a 개발자, I want to Kubernetes Service를 통해 AI Agent 앱에 안정적으로 접근하고 싶다, so that Pod IP 변경에 관계없이 일관된 엔드포인트를 사용할 수 있다.

#### Acceptance Criteria

1. THE Service_Manifest SHALL ClusterIP 타입으로 AI_Agent_App Pod들에 대한 내부 접근을 제공하며, Deployment의 Pod 라벨(app, component)과 일치하는 selector를 구성한다
2. THE Service_Manifest SHALL TCP 프로토콜로 포트 80을 targetPort 8000으로 매핑하고, 포트 이름을 "http"로 지정한다
3. WHERE 로컬 개발 환경(Docker Desktop Kubernetes)에서, THE Service_Manifest SHALL LoadBalancer 타입으로 외부 접근을 허용하여 localhost를 통해 포트 80으로 접근 가능하게 한다
4. THE Service_Manifest SHALL "ai-agent-ops" Namespace 내에 배포되어 클러스터 내부에서 `ai-agent-app.ai-agent-ops.svc.cluster.local` DNS 이름으로 접근 가능하게 한다
5. IF AI_Agent_App Pod가 readinessProbe에 실패한 상태일 경우, THEN THE Service_Manifest SHALL 해당 Pod를 엔드포인트 목록에서 제외하여 트래픽을 라우팅하지 않는다

### Requirement 4: 환경 설정 관리 (ConfigMap 및 Secret)

**User Story:** As a DevOps 엔지니어, I want to 환경 설정과 민감 정보를 Kubernetes 네이티브 방식으로 관리하고 싶다, so that 설정 변경 시 이미지 재빌드 없이 반영할 수 있다.

#### Acceptance Criteria

1. THE ConfigMap SHALL LOG_LEVEL(기본값: INFO, 허용값: DEBUG|INFO|WARNING|ERROR), DEBUG_MODE(기본값: false), SESSION_TTL_HOURS(기본값: 24) 비민감 환경 변수를 키-값 쌍으로 저장한다
2. THE Secret SHALL OPENAI_API_KEY, DATABASE_URL, ELASTICSEARCH_URL 필수 민감 환경 변수와 ANTHROPIC_API_KEY, GOOGLE_API_KEY 선택 민감 환경 변수를 base64 인코딩하여 저장한다
3. WHEN ConfigMap 값이 변경될 때, THE K8s_Cluster SHALL ConfigMap을 Volume으로 마운트하여 Pod 재시작 없이 변경된 값을 파일 시스템에 반영한다
4. IF 선택적 Secret 키(ANTHROPIC_API_KEY, GOOGLE_API_KEY)가 정의되지 않은 경우, THEN THE Deployment_Manifest SHALL optional 플래그(optional: true)를 설정하여 Pod가 정상 시작되도록 한다
5. IF 필수 Secret 키(OPENAI_API_KEY, DATABASE_URL, ELASTICSEARCH_URL)가 누락된 경우, THEN THE K8s_Cluster SHALL Pod를 시작하지 않고 컨테이너 상태를 CreateContainerConfigError로 표시한다

### Requirement 5: 의존 서비스 배포 (PostgreSQL, Elasticsearch)

**User Story:** As a DevOps 엔지니어, I want to PostgreSQL과 Elasticsearch를 Kubernetes 내에서 함께 운영하고 싶다, so that 애플리케이션과 동일한 네트워크에서 의존 서비스에 접근할 수 있다.

#### Acceptance Criteria

1. THE K8s_Cluster SHALL PostgreSQL을 StatefulSet으로 배포하고 최소 1Gi 용량의 PersistentVolumeClaim을 통해 데이터를 영속 저장한다
2. THE K8s_Cluster SHALL Elasticsearch 8.x를 StatefulSet으로 배포하고 최소 2Gi 용량의 PersistentVolumeClaim을 통해 데이터를 영속 저장한다
3. THE K8s_Cluster SHALL PostgreSQL에 대해 포트 5432, Elasticsearch에 대해 포트 9200을 노출하는 ClusterIP Service를 각각 생성하여, AI_Agent_App이 내부 DNS 이름(서비스명.네임스페이스.svc.cluster.local)으로 접근할 수 있게 한다
4. WHEN PostgreSQL Pod가 시작될 때, THE K8s_Cluster SHALL 환경 변수(POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)를 Secret에서 참조하여 초기 데이터베이스와 사용자를 생성한다
5. IF PostgreSQL 또는 Elasticsearch Pod가 비정상 종료될 경우, THEN THE K8s_Cluster SHALL PersistentVolume의 reclaimPolicy를 Retain으로 설정하여 데이터 손실을 방지한다
6. THE K8s_Cluster SHALL PostgreSQL StatefulSet에 TCP 포트 5432 연결 확인 readinessProbe를, Elasticsearch StatefulSet에 HTTP GET /_cluster/health 엔드포인트(포트 9200) readinessProbe를 구성하여 서비스 준비 상태를 검증한다

### Requirement 6: 네임스페이스 격리 및 리소스 구성

**User Story:** As a DevOps 엔지니어, I want to 전용 네임스페이스를 사용하여 리소스를 격리하고 싶다, so that 다른 워크로드와 충돌 없이 독립적으로 관리할 수 있다.

#### Acceptance Criteria

1. THE K8s_Cluster SHALL "ai-agent-ops"라는 전용 Namespace를 생성한다
2. THE Deployment_Manifest SHALL 모든 리소스(Deployment, StatefulSet, Service, ConfigMap, Secret, HPA)를 "ai-agent-ops" Namespace 내에 배포한다
3. THE K8s_Cluster SHALL 네임스페이스 수준의 ResourceQuota를 설정하여 CPU 요청 합계 최대 4코어, 메모리 요청 합계 최대 8Gi, Pod 최대 20개로 전체 리소스 사용량을 제한한다
4. THE K8s_Cluster SHALL LimitRange를 설정하여 개별 컨테이너의 기본 리소스 요청(CPU: 100m, 메모리: 128Mi)과 기본 제한(CPU: 500m, 메모리: 512Mi)을 적용한다
5. IF 신규 Pod 생성 시 ResourceQuota를 초과할 경우, THEN THE K8s_Cluster SHALL 해당 Pod 생성을 거부하고 쿼터 초과를 나타내는 에러 메시지를 반환한다

### Requirement 7: 자동 스케일링 (HPA)

**User Story:** As a DevOps 엔지니어, I want to 트래픽 증가 시 자동으로 Pod 수를 확장하고 싶다, so that 서비스 가용성을 유지할 수 있다.

#### Acceptance Criteria

1. WHEN AI_Agent_App Pod의 평균 CPU 사용률이 70%를 초과할 때, THE HPA SHALL Pod replica 수를 자동으로 증가시킨다
2. THE HPA SHALL 최소 2개, 최대 10개 replica를 유지한다
3. WHEN AI_Agent_App Pod의 평균 CPU 사용률이 70% 이하로 300초(5분) 이상 유지될 때, THE HPA SHALL Pod 수를 최소 replica 수(2개)까지 점진적으로 축소한다
4. IF HPA가 최대 replica 수(10개)에 도달한 상태에서 평균 CPU 사용률이 여전히 70%를 초과할 경우, THEN THE HPA SHALL 추가 확장 없이 현재 replica 수를 유지하고 스케일링 이벤트를 기록한다
5. THE HPA SHALL scale-down 안정화 윈도우를 300초로 설정하여 Pod 수의 빈번한 증감(flapping)을 방지한다

### Requirement 8: 배포 자동화 스크립트

**User Story:** As a 개발자, I want to 단일 명령으로 전체 Kubernetes 배포를 실행하고 싶다, so that 복잡한 배포 절차를 단순화할 수 있다.

#### Acceptance Criteria

1. WHEN 배포 스크립트가 환경 인자(dev 또는 prod)와 함께 실행될 때, THE AI_Agent_App SHALL Namespace 생성, ConfigMap/Secret 적용, 의존 서비스 배포(PostgreSQL, Elasticsearch), 애플리케이션 배포 순서로 실행하며, 각 단계의 리소스가 Ready 상태가 된 것을 확인한 후 다음 단계로 진행한다
2. THE AI_Agent_App SHALL Kustomize를 사용하여 개발(dev)과 운영(prod) 환경을 분리하되, 환경별로 replica 수, 리소스 requests/limits, 환경 변수 값을 오버레이로 구분한다
3. IF 배포 중 특정 단계에서 에러가 발생하거나 리소스가 300초 이내에 Ready 상태에 도달하지 못할 경우, THEN THE AI_Agent_App SHALL 실패한 단계명과 에러 메시지를 표준 에러로 출력하고, 이미 성공적으로 완료된 이전 단계의 리소스는 롤백하지 않고 유지한다
4. IF 배포 스크립트 실행 시 kubectl이 클러스터에 연결할 수 없는 경우, THEN THE AI_Agent_App SHALL 클러스터 연결 실패를 알리는 에러 메시지를 출력하고 배포를 시작하지 않는다
5. WHEN 배포 스크립트가 각 단계를 실행할 때, THE AI_Agent_App SHALL 현재 실행 중인 단계명과 완료 상태를 표준 출력으로 표시한다

### Requirement 9: k9s 모니터링 및 관리 지원

**User Story:** As a DevOps 엔지니어, I want to k9s를 통해 배포된 리소스를 실시간으로 모니터링하고 관리하고 싶다, so that 운영 상태를 신속하게 파악하고 문제에 대응할 수 있다.

#### Acceptance Criteria

1. THE Deployment_Manifest SHALL 모든 리소스에 라벨 app, component, version을 부여하며, 동일 애플리케이션에 속한 리소스는 동일한 app 라벨 값을 사용하여 k9s에서 라벨 기반 필터링이 가능하도록 한다
2. THE Deployment_Manifest SHALL Pod에 annotation으로 배포 시간(deploy-timestamp, ISO 8601 형식)과 이미지 버전(app-version, 시맨틱 버전 형식)을 추가하여 k9s에서 상세 정보를 확인할 수 있도록 한다
3. THE AI_Agent_App SHALL 로그를 stdout으로 출력하며, 각 로그 엔트리는 JSON 형식으로 최소 timestamp(ISO 8601), level(DEBUG/INFO/WARNING/ERROR), message, logger 필드를 포함한다
4. THE K8s_Cluster SHALL metrics-server를 배포하여 k9s에서 Pod별 CPU 및 메모리 사용량을 60초 이내의 갱신 주기로 조회할 수 있도록 한다
5. IF AI_Agent_App에서 요청 처리 중 에러가 발생할 경우, THEN THE AI_Agent_App SHALL 에러 로그 엔트리에 timestamp, level, message, logger 외에 추가로 error_type과 trace_id 필드를 포함하여 k9s 로그 뷰어에서 문제 추적이 가능하도록 한다
