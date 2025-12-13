ARG BUILD_FROM
FROM $BUILD_FROM

SHELL ["/bin/sh", "-c"]

WORKDIR /opt/predbat

# Install Python and pip
RUN apk add --no-cache python3 py3-pip git

# Clone the Predbat repository to get the code
ARG BUILD_VERSION
RUN git clone --depth 1 --branch main https://github.com/markgraham924/batpred-alphaess.git /tmp/predbat && \
    mkdir -p /opt/predbat/apps && \
    cp -r /tmp/predbat/apps/predbat /opt/predbat/apps/predbat && \
    cp /tmp/predbat/requirements.txt /tmp/requirements.txt && \
    rm -rf /tmp/predbat

# Install project requirements
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# Copy add-on runtime files
COPY rootfs/ /

# Ensure run script is executable
RUN chmod +x /run.sh && \
    chmod +x /etc/s6-overlay/s6-rc.d/predbat/run

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="markgraham924" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
