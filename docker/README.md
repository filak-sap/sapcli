# sapcli Docker image

Avoid the need to mess up with installation of Python-3.6

# Usage

Start an ABAP system:

```bash
docker run -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -p 3200:3202 -p 3300:3302 -p 50001:50003 -h dlms4hana --name sap3 abapimage
```

Install sapcli and create a convenience tag sapcli:

```bash
docker pull docker.wdf.sap.corp:51190/automation/sapcli:latest
docker tag docker.wdf.sap.corp:51190/automation/sapcli:latest sapcli
```

List objects from the package SOOL:

```bash
docker run -it --rm --link sap3 sapcli \
           --ashost dlms4hana --client 100 --skip-ssl-validation --port 50001 --user DEVELOPER --password 'Welcome1!' \
           package list sool
```

Yes, we linked the containers and thus the port 50001 is OK because we are connecting directly to the docker container

## Advanced

Without the linking, we would need to connect to the port 5003 and the docker host IP:

```bash
docker run -it --rm sapcli \
           --ashost 172.17.0.1 --client 100 --skip-ssl-validation --port 50003 --user DEVELOPER --password 'Welcome1!' \
           package list sool
```

# Example: Activate a class

```bash
docker run -it --rm --link sap3 sapcli \
           --ashost dlms4hana --client 100 --skip-ssl-validation --port 50001 --user DEVELOPER --password 'Welcome1!' \
           class activate CL_OTR_LONGTEXT
```
