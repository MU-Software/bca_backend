![B.Ca title image](./.github/readme/title.png)
# B.Ca API 백엔드 저장소
B.Ca는 제 졸업작품으로 진행된, 명함을 중점으로 한 커뮤니케이션 메신저 프로젝트입니다.  
이 저장소는 Python으로 작성된 HTTP API 서버 코드를 포함하고 있으며, [FROST 프로젝트](https://github.com/MU-software/frost)를 기반으로 합니다.  

# 프로젝트 구조
이 프로젝트는 간단하게 안드로이드 클라이언트, 현재 보고계신 API 서버, 그리고 작업 스케쥴러로 이루어져 있습니다.  
* 안드로이드 클라이언트: 제곧내입니다(...)  
* API 백엔드 서버: 현재 보시고 계신 이 저장소 입니다. 모든 HTTP REST 요청을 처리합니다.  
* 작업 스케줄러: 작업 스케줄러는 유저 동기화 DB 파일들 수정과 같은 오래 걸리는 작업들을 API 서버 대신 수행합니다. AWS SQS와 Lambda 위에서 돌아갑니다.  

### AWS 의존성
이 프로젝트는 AWS의 몇몇 서비스 위에서 동작합니다. 예를 들면, 작업 스케줄러는 AWS SQS와 AWS Lambda 위에서 동작하는 것을 의도하여 작성되었습니다. 아래 표는 AWS의 어떠한 서비스를 사용하는지를 나타냅니다.  
서비스명 | 필수 여부 | 사용처
|   :----:   |  :----:  | :----
EC2          |   | API 서버용 컴퓨팅 인스턴스. 당연하지만 다른 컴퓨팅 인스턴스를 사용하신다면 필수는 아닙니다.  
S3           | O | 유저의 동기화 될 DB 파일들이나 유저가 업로드한 파일을 저장할 파일 스토리지.  
RDS          |   | API 서버는 PostgreSQL이나 SQLite3를 현재 지원합니다. (MySQL/MariaDB도 지원할 수도 있습니다만, 테스트하지 않았습니다.) 만약 SQLite3를 DB로 사용한다면 RDS는 필요 없으실거에요.  
ElastiCache  | O | Redis, 길게 말할 것이 없네요.  
SQS          | O | 작업 스케줄러의 메시지 큐로 사용됩니다. 하나의 작업마다 하나의 Lambda 인스턴스가 실행됩니다.  
Lambda       | O | 작업 스케줄러의 Worker 인스턴스로 사용됩니다.  
SES          |   | 회원가입이나 비밀번호 변경 등에 사용될 메일과 관련한 기능에 사용됩니다. 단, 메일 기능 자체를 `env_collection`에서 끄실 수 있습니다..  

### Firebase 의존성
이 프로젝트는 채팅 메시지 푸시 알람 기능 구현을 위해 Firebase Cloud Messaging(FCM)을 사용했습니다.  

## API 서버
위에서 언급한대로 코드베이스가 [FROST 프로젝트](https://github.com/MU-software/frost)를 기반으로 작성된만큼, 먼저 FROST의 README를 먼저 읽어주시기 바랍니다.  

### environment
환경변수를 포함한 프로젝트의 각종 변수를 env_collection을 통해 관리할 수 있습니다. 이 섹션에서는 이 프로젝트에서 사용되는 변수만을 다룹니다. 그 외의 변수들은 FROST의 README를 참조해주세요.  
Key                     | Required | Explain
| :----:                |  :----:  | :----
`AWS_REGION`            | O | AWS를 다루기 위한 Boto3 라이브러리에서 사용됩니다.  
`AWS_ACCESS_KEY_ID`     | O | AWS를 다루기 위한 Boto3 라이브러리에서 사용됩니다.  
`AWS_SECRET_ACCESS_KEY` | O | AWS를 다루기 위한 Boto3 라이브러리에서 사용됩니다.  
`AWS_S3_BUCKET_NAME`    | O | 유저의 동기화 될 DB 파일들이나 유저가 업로드한 파일은 현재 AWS S3에 저장됩니다. 타겟 S3의 이름을 명시해주세요.
`AWS_TASK_SQS_URL`      | O | 시간이 오래 걸릴 수 있는 작업들을 작업 스케줄러로 보낼 때 사용할 메시지 큐의 URL을 적어주세요, 다만, 위의 `AWS_S3_BUCKET_NAME`에서는 이름을 입력했다면, 여기서는 SQS의 URL을 입력해야 함을 주의해주세요.  
`FIREBASE_CERTIFICATE`  | O | 채팅의 메시지 푸시 알림에 FCM이 사용됩니다.

### DB / Redis
근본이 되는 FROST와 유사하게, (유저의 정보들을 저장하기 위한) DB나 (유효하지 않은 토큰을 저장하기 위한, 또 작업 스케줄러에서의 파일 작업 중 임계 영역 문제 해결을 위하여) Redis를 필요로 합니다. `env_collection`에서 각 구성요소의 주소를 입력해주세요.

### Bugs
여러모로 급하게 진행된 만큼 ~~코드가 더럽고~~ 버그가 많습니다ㅠㅜ 만약 버그를 발견하신다면, 이슈를 보내주세요!
