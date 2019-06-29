FROM fedora
LABEL maintainer="jakub.filak@sap.com"
LABEL home="https://github.wdf.sap.corp/I335255/sapcli"

COPY sapcli.tar.gz /var/tmp/
RUN mkdir -p /opt/sapcli
RUN tar -C /opt/sapcli -zxf /var/tmp/sapcli.tar.gz
RUN test -e /opt/sapcli/bin/sapcli

RUN dnf install -y python3 python3-requests; dnf clean all
RUN ln -sf /opt/sapcli/sap /usr/lib/python3.7/site-packages/
RUN ln -sf /opt/sapcli/bin/sapcli /usr/bin/sapcli

ENTRYPOINT ["/usr/bin/python3", "/opt/sapcli/bin/sapcli"]
