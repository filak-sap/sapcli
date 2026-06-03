FROM almalinux:9
LABEL maintainer="jakub.filak@sap.com"
LABEL home="https://github.wdf.sap.corp/I335255/sapcli"

ARG NWRFCSDK_DIST
ENV TMP_INST_DIR=/var/tmp/inst
ENV SAPNWRFC_HOME=/opt/sap/nwrfcsdk
ENV PYTHONPATH=/usr/local/lib64/python3.12/site-packages

RUN mkdir -p ${TMP_INST_DIR}

COPY sapcli.tar.gz ${TMP_INST_DIR}
COPY ${NWRFCSDK_DIST} ${TMP_INST_DIR}

COPY SAPNetCA_G2.crt /etc/pki/ca-trust/source/anchors
RUN update-ca-trust

RUN dnf install -y 'dnf-command(config-manager)' \
 && dnf config-manager --enable crb \
 && dnf update -y \
 && dnf install -y python3.12 python3.12-requests python3.12-pyyaml python3.12-pip python3.12-devel python3.12-Cython \
        gcc gcc-c++ openldap-devel unzip which git epel-release glibc-langpack-en \
 && ln -sf $(which pip3.12) /usr/local/bin/pip \
 && ln -sf $(which python3.12) /usr/local/bin/python \
 && ln -sf $(which python3.12) /usr/bin/python3 \
 && python --version \
 && python3 --version \
 && pip install python-ldap \
 && pip --version

ENV LANG=en_US.UTF-8
RUN echo -e "LANG=en_US.UTF-8\nLC_ALL=en_US.UTF-8" > /etc/locale.conf
RUN echo -e "LANG=en_US.UTF-8\nLC_ALL=en_US.UTF-8" > /etc/profile.d/locale.sh

RUN unzip ${TMP_INST_DIR}/${NWRFCSDK_DIST} -d ${TMP_INST_DIR}/nwrfcsdk_dist && \
    echo "** Unpacking NWRFCSDK dist" && mkdir -p $(dirname ${SAPNWRFC_HOME}) && \
    echo "** Installing NWRFCSDK" && cp -r /${TMP_INST_DIR}/nwrfcsdk_dist/nwrfcsdk $(dirname ${SAPNWRFC_HOME}) && \
    echo "** Creating ld.so.conf file" && echo ${SAPNWRFC_HOME}/lib > /etc/ld.so.conf.d/nwrfcsdk.conf && \
    echo "** Updating dynamic library cache" && ldconfig

RUN echo "** Clonning github.com/SAP/pyrfc" && cd /tmp/ && git clone --depth 1 --no-tags https://github.com/SAP/PyRFC && cd PyRFC && \
    echo "** Installing Python3 PyNWRFC" && pip install . && \
    echo "** Verifying PyRFC installation" && cd / && echo "import pyrfc" | python3

RUN dnf erase -y python3.12-devel gcc gcc-c++ openldap-devel unzip which git && dnf clean all

RUN mkdir -p /opt/sapcli && \
    tar -C /opt/sapcli -zxf ${TMP_INST_DIR}/sapcli.tar.gz && \
    test -e /opt/sapcli/bin/sapcli && \
    pip install pyodata platformdirs && \
    ln -sf /opt/sapcli/sap /usr/lib/$(basename $(readlink /usr/bin/python3))/site-packages/ && \
    ln -sf /opt/sapcli/bin/sapcli /usr/bin/sapcli && \
    sapcli --help && \
    python -c "from sap.platform.language import locale_lang_sap_code; print(locale_lang_sap_code())"

ENTRYPOINT ["/usr/bin/python3", "/opt/sapcli/bin/sapcli"]
