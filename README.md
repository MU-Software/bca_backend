![B.Ca title image](./.github/readme/title.png)
# B.Ca API backend repository
> This project is based on [MU-Software/frost](https://github.com/MU-software/frost).  
> Check this out if you are interested in building a RESTful API and generating an OpenAPI 3.0 documentation automatically with less code!  

> [여기](README-ko_kr.md)에 한국어 버전의 README가 있어요!  
> [Click here](README-ko_kr.md) to read a README written in Korean!  

B.Ca is a communication messenger project focusing on a business card, which was conducted as a graduation project.  
This repository contains the main API backend server code (which is based on [FROST project](https://github.com/MU-software/frost)) and a Task Scheduler([Celery](https://docs.celeryq.dev/) Worker).  

## Project structure
The project consists of an Android client, this API server, and a Task Scheduler.  
* Android client: The title says all.  
* API backend server: This repository. This handles all HTTP REST requests.  
* Task scheduler: Task scheduler, which is implemented as a Celery worker, handles some batch tasks that can take much time, like user db file modification. Originally, this was on a separate repository, but it was merged to this repository while migrating to Celery worker.

## API Server
Since this codebase is based on [FROST project](https://github.com/MU-software/frost), Please read the FROST's README first to get base information (like environment variables). Additionally, this project uses Redis as Celery's backend & broker and also uses it as a lock to solve a critical section problem that multiple workers can access and try to modify the same file.  
This repository requires Python 3.10 or above.

### Firebase dependency
This project uses Firebase Cloud Messaging(FCM) on chat message notification push implementation.  

#### Environment variables
Key                     | Explain
|        :----:         | :----
`FIREBASE_CERTIFICATE`  | Firebase Cloud Messaging(FCM) is used on chat message notification push implementation.  

### Previous AWS dependencies
Originally, this project had dependencies on some AWS services (like S3, SQS, Lambda) to implement a task scheduler. But, after migrating and rewriting the task scheduler to Celery, the task scheduler was merged on this repository, and also AWS dependencies were removed. (That repository remains only for historical records use in graduation projects and no longer works.) The table below explains what services on AWS were used on this project.  
Service Name | Usage
|   :----:   | :----
S3           | File storage for user-db files. User-uploaded files will be stored on API server.  
SQS          | Used for message queues in the task scheduler. One lambda instance is triggered per task job.  
Lambda       | Used as task scheduler's worker instances.  

#### Environment variables
These environment variables were used when we had a dependency on AWS services. You must not set these variables as we don't support AWS anymore.  
Key                     | Explain
| :----:                | :----
`AWS_REGION`            | Boto3 needed this.  
`AWS_ACCESS_KEY_ID`     | Boto3 needed this.  
`AWS_SECRET_ACCESS_KEY` | Boto3 needed this.  
`AWS_S3_BUCKET_NAME`    | We stored user-db files and user-uploaded files on AWS S3, so we needed to specify the name of a target S3 bucket.  
`AWS_TASK_SQS_URL`      | We needed to send long-term task jobs to Task Scheduler, so we were using SQS as message queue. Please be aware that unlike the variables above, you needed to specify a URL other than a name.  

### Bugs
This project has a lot of bugs as it was carried out in a hurry. If you find a bug, please create the issue.
