FROM fedora
LABEL maintainer="jakub.filak@sap.com"
LABEL home="https://github.wdf.sap.corp/I335255/sapcli"

COPY sapcli.tar.gz /var/tmp/

RUN mkdir -p /opt/sapcli && \
    tar -C /opt/sapcli -zxf /var/tmp/sapcli.tar.gz && \
    test -e /opt/sapcli/bin/sapcli && \
    dnf install -y python3 python3-requests; dnf clean all && \
    ln -sf /opt/sapcli/sap /usr/lib/$(readlink /usr/bin/python3)/site-packages/ && \
    ln -sf /opt/sapcli/bin/sapcli /usr/bin/sapcli

ENTRYPOINT ["/usr/bin/python3", "/opt/sapcli/bin/sapcli"]
