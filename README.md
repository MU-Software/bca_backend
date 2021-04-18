# B.Ca babackend ckend
Flask project for B.Ca Project


## Setup & Run
### Setup
#### Windows
```POWERSHELL
git clone "https://github.com/bca-lab/bca_backend.git"
cd bca_backend
python -m venv ./
./Scripts/activate
python -m pip install -U -r "requirements-dev.txt"
```
Copy and paste this to Powershell.  
You have to install git and Python3.9 (or above) to run these commands

#### Debian based(Ubuntu/Linux Mint/etc.)
```BASH
git clone "https://github.com/bca-lab/bca_backend.git"
cd bca_backend
python3.9 -m venv ./
source ./bin/activate
python3.9 -m pip install -U -r "requirements-dev.txt"
```
Copy and paste this to Bash shell.  
You also needs `python3.9`, `python3.9-pip`, `python3.9-venv` to run these commands.

### Run
Run server with ```python -m flask run``` on Windows, or ```python3.9 -m flask run``` on Linux.  
You can set some environment variables below.

Key               | Explain
----              | ----
`DB_URL`          | Database URL to connect, `sqlite:///:memory:` if not set.
`FLASK_ENV`       | Same as Flask's `FLASK_ENV`, see [Flask document](https://flask.palletsprojects.com/en/master/config/)
`RESTAPI_VERSION` | This value will be included in route URL. `dev` if not set.<br>ex) `/dev/account/login`, `/v2/posts/123456`
`SECRET_KEY`      | Secret key used in JWT, session cookie, etc. Random string will be applied if not set. This is same as Flask's `SECRET_KEY`, see [Flask document](https://flask.palletsprojects.com/en/master/config/#SECRET_KEY)

## Code convension
  - Max line length to `120`
