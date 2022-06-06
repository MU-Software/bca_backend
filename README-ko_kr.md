![B.Ca title image](./.github/readme/title.png)
# B.Ca API 백엔드 저장소
> 이 프로젝트는 [MU-Software/frost](https://github.com/MU-software/frost)에 기반하고 있습니다. 관심이 있으시다면 한번 확인해보세요!   
> 더 적은 코드로 RESTful한 API를 작성하고, 문서 자동화를 경험하실 수 있어요!  

> [여기](README.md)에 영어 버전의 README가 준비되어 있습니다!  
> [Click here](README.md) to read a README written in English.  

B.Ca는 제 졸업작품으로 진행된, 명함을 중점으로 한 커뮤니케이션 메신저 프로젝트입니다.  
본 저장소는 [FROST 프로젝트](https://github.com/MU-software/frost)를 기반으로 작성된 HTTP API 서버 코드와 작업 스케줄러([Celery](https://docs.celeryq.dev/) Worker)를 포함하고 있습니다.  

## 프로젝트 구조
이 프로젝트는 간단하게 안드로이드 클라이언트, 현재 보고계신 API 서버, 그리고 작업 스케줄러(Celery worker)로 이루어져 있습니다.  
* 안드로이드 클라이언트: 제곧내입니다(...)  
* API 백엔드 서버: 현재 보시고 계신 이 저장소 입니다. 모든 HTTP REST 요청을 처리합니다.  
* 작업 스케줄러: Celery worker로 동작하도록 작성된 작업 스케줄러는 유저 동기화 DB 파일 수정과 같은 오래 걸리는 작업들을 API 서버 대신 수행합니다. 원래 별개의 저장소에서 관리되고 있었지만, Celery로 재작성되면서 이 저장소에 병합되었습니다.  

## API 서버
위에서 언급한대로 코드베이스가 [FROST 프로젝트](https://github.com/MU-software/frost)를 기반으로 작성된만큼, 기본적으로 설정해야 하는 FROST의 환경 변수와 같은 설명은 FROST의 README를 참고해주시기 바랍니다. 추가적으로 본 프로젝트는 FROST의 Redis 사용 용례에 더해서 Celery의 backend와 broker로서, 그리고 다중 Worker가 같은 파일에 접근하는 임계영역문제를 해결하기 위한 Lock으로서로도 사용됩니다.  
본 저장소의 코드는 Python 3.10 이상에서 동작하도록 작성되었습니다.

### Firebase 의존성
이 프로젝트는 채팅 메시지 푸시 알람 기능 구현을 위해 Firebase Cloud Messaging(FCM)을 사용하고 있습니다.  
#### 환경 변수
아래는 FCM 동작에 필요한 환경 변수입니다.  
Key                     | Required | Explain
| :----:                |  :----:  | :----
`FIREBASE_CERTIFICATE`  | O | 채팅의 메시지 푸시 알림에 FCM이 사용됩니다.

### 과거 AWS 의존성
원래 이 프로젝트는 작업 스케줄러를 구현하기 위해 일부 AWS 서비스(S3, SQS, Lambda 등)에 의존했습니다. 그러나 작업 스케줄러를 Celery로 마이그레이션하고 다시 작성한 후, 작업 스케줄러는 이 저장소에서 병합되었으며 프로젝트의 AWS 종속성도 제거되었습니다. (옛 스케줄러 저장소는 졸업 작품에 사용되었다는 역사적 기록으로서만 남아있으며 더 이상 작동하지 않습니다.) 아래 표는 과거 AWS의 어떠한 서비스에 의존성을 가지고 있었는지를 나타냅니다.  
서비스명 | 사용 용도
|   :----:   | :----
S3           | 유저의 동기화 될 DB 파일들을 저장할 파일 스토리지. 유저가 업로드한 파일은 API 서버에 저장됩니다.  
SQS          | 작업 스케줄러의 메시지 큐로 사용되었습니다. 하나의 작업마다 하나의 Lambda 인스턴스가 실행됩니다.  
Lambda       | 작업 스케줄러의 Worker 인스턴스로 사용되었습니다.  

#### 환경 변수
아래는 AWS 의존성을 가질 때 쓰이던 환경 변수입니다. 더 이상 사용하지 마세요.  
Key                     | Explain
| :----:                | :----
`AWS_REGION`            | AWS를 다루기 위한 Boto3 라이브러리에서 사용됐었습니다.  
`AWS_ACCESS_KEY_ID`     | AWS를 다루기 위한 Boto3 라이브러리에서 사용됐었습니다.  
`AWS_SECRET_ACCESS_KEY` | AWS를 다루기 위한 Boto3 라이브러리에서 사용됐었습니다.  
`AWS_S3_BUCKET_NAME`    | 유저의 동기화 DB 파일들은 과거 AWS S3에 저장됐었습니다. 타겟 S3의 이름을 명시해줘야 했습니다.
`AWS_TASK_SQS_URL`      | 시간이 오래 걸릴 수 있는 작업들을 작업 스케줄러로 보낼 때 사용할 메시지 큐의 URL을 적어주어야 했습니다, 다만, 위의 `AWS_S3_BUCKET_NAME`에서는 이름을 입력했다면, 여기서는 SQS의 URL을 입력해야 함을 주의해주세요.  

## Bugs
만약 버그를 발견하신다면, Github에서 이슈를 열어주세요!
