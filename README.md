Downstream SAP fork for untested features and secrete stuff such as APIs for Data Extraction.

Please, use the upstream repo for new code [https://github.com/jfilak/sapcli](https://github.com/jfilak/sapcli).

## Install SAP version

🛑 ✋ !! *DO NOT install the package `sapcli` from PyPI because that is not a completely different package* !!

### pip

Create the file `~/.pip/pip.conf`

```
[global]
index-url = https://USER:TOKEN@common.repositories.cloud.sap/artifactory/api/pypi/sapcli/simple
extra-index-url=https://pypi.org/simple
```

Run the command:
```bash
pip install internal-sapcli
```

### uv and pipx

Create the file `~/.config/uv/uv.toml`

```
[[index]]
name="sapcli"
url = "https://common.repositories.cloud.sap/artifactory/api/pypi/sapcli/simple"
default = true

[[index]]
name = "pypi"
url = "https://pypi.org/simple"
```

Run the uv command to login to the SAP repository:
```bash
uv auth login https://common.repositories.cloud.sap/artifactory/api/pypi/sapcli --username USER --password TOKEN
```

Run the command to install the SAP version:
```bash
uv pip uninstall --system internal-sapcli
```

or pipx
```bash
pipx install internal-sapcli
```

## Maintenance

### Fork update process

1. git clone https://github.com/jfilak/sapcli
2. cd sapcli
3. git remote add sap\_fork https://github.wdf.sap.corp/factory/sapcli
4. git checkout -b sap\_fork\_master sap\_fork/master
7. git rebase origin/master
8. git push sap\_fork HEAD:master -f
