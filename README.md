![B.Ca title image](./.github/readme/title.png)
# B.Ca API backend repository
B.Ca is a communication messenger project focusing on business card, which was cunducted as a graduation work.  
This repository contains the main API backend server code written in Python.  
Also, this repository is based on [FROST project](https://github.com/MU-software/frost).  

# Project structure
The project consists of an Android client, this API server, and a task scheduler.  
* Android client: The title says all.  
* API backend server: This repository, this handles all HTTP REST requests.  
* Task scheduler: Task scheduler handles some batch tasks that can take much time, like user db file modifications. This runs on AWS SQS and Lambda.

### AWS dependencies
This project uses some services of AWS. For example, This API server was written assuming that it would run on an AWS EC2 instance. The table below shows which services are used in the project backend.  
Service Name | Required | Usage
|   :----:   |  :----:  | :----
EC2          |   | Compute instance for API server.  
S3           | O | File storage for user-db files and user-uploaded files.  
RDS          |   | API server natively supports PostgreSQL or SQLite3, but maybe it can handle MySQL/MariaDB, too (not tested tho). You don't need this if you use SQLite3.  
ElastiCache  | O | Redis, not to mention long.  
SQS          | O | Used for message queues in the task scheduler. One lambda instance is triggered per task job.  
Lambda       | O | Used as task scheduler's worker instances.  
SES          |   | Used to send mail on account-related matters such as account registration, password change, etc. This function can be off completely on `env_collection`.  

### Firebase dependency
This project uses Firebase Cloud Messaging(FCM) on chat message notification push implementation.  

## API Server
Since codebase is based on [FROST project](https://github.com/MU-software/frost) (as I said earlier), lots of things goes similarly to that project. Please read the FROST's README first.  

### environment
You can manage environment settings using env_collection. This section documents only the variables used in this project only. For other variables, please refer to the explanation of FROST. 
Key                     | Required | Explain
| :----:                |  :----:  | :----
`AWS_REGION`            | O | Boto3 needs this.  
`AWS_ACCESS_KEY_ID`     | O | Boto3 needs this.  
`AWS_SECRET_ACCESS_KEY` | O | Boto3 needs this.  
`AWS_S3_BUCKET_NAME`    | O | We save user-db files and user-uploaded files on AWS S3, so we need to specify the name of a target S3 bucket.  
`AWS_TASK_SQS_URL`      | O | We need to send long-term task jobs to Task Scheduler, so we are using SQS as message queue. Please be aware that unlike the variables above, you need to specify a URL other than a name.  
`FIREBASE_CERTIFICATE`  | O | Firebase Cloud Messaging(FCM) is used on chat message notification push implementation.  

### DB / Redis
As the original FROST needs DB (for storing user informational resources) and Redis(for storing invoked user tokens, etc.), this project also needs those. Please designate it in `env_collection`.

### Bugs
This project has a lot of bugs as it was carried out in a hurry. If you find a bug, please create the issue.
