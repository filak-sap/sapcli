FROM fedora:37
LABEL maintainer="jakub.filak@sap.com"
LABEL home="https://github.wdf.sap.corp/I335255/sapcli"

ARG NWRFCSDK_DIST
ENV TMP_INST_DIR=/var/tmp/inst
ENV SAPNWRFC_HOME=/opt/sap/nwrfcsdk

RUN mkdir -p ${TMP_INST_DIR}

COPY sapcli.tar.gz ${TMP_INST_DIR}
COPY ${NWRFCSDK_DIST} ${TMP_INST_DIR}

COPY SAPNetCA_G2.crt /etc/pki/ca-trust/source/anchors
RUN update-ca-trust

RUN dnf install -y python3 python3-requests python3-pyyaml python3-pip python3-devel gcc-c++ unzip

RUN unzip ${TMP_INST_DIR}/${NWRFCSDK_DIST} -d ${TMP_INST_DIR}/nwrfcsdk_dist && \
    echo "** Unpacking NWRFCSDK dist" && mkdir -p $(dirname ${SAPNWRFC_HOME}) && \
    echo "** Installing NWRFCSDK" && cp -r /${TMP_INST_DIR}/nwrfcsdk_dist/nwrfcsdk $(dirname ${SAPNWRFC_HOME}) && \
    echo "** Creating ld.so.conf file" && echo ${SAPNWRFC_HOME}/lib > /etc/ld.so.conf.d/nwrfcsdk.conf && \
    echo "** Updating dynamic library cache" && ldconfig && \
    echo "** Installing Python3 PyNWRFC" && pip3 install pyrfc && \
    echo "** Verifying PyRFC installation" && echo "import pyrfc" | python3

RUN dnf erase -y python3-devel gcc-c++ unzip && dnf clean all

RUN mkdir -p /opt/sapcli && \
    tar -C /opt/sapcli -zxf ${TMP_INST_DIR}/sapcli.tar.gz && \
    test -e /opt/sapcli/bin/sapcli && \
    pip install pyodata && \
    ln -sf /opt/sapcli/sap /usr/lib/$(readlink /usr/bin/python3)/site-packages/ && \
    ln -sf /opt/sapcli/bin/sapcli /usr/bin/sapcli && \
    sapcli --help

ENTRYPOINT ["/usr/bin/python3", "/opt/sapcli/bin/sapcli"]
