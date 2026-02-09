ARG BUILD_FROM
FROM $BUILD_FROM

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install requirements for add-on
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    jq

# Create app directory
WORKDIR /opt/fortinet-zoho-sync

# Copy application files
COPY rootfs /

# Install Python requirements
RUN pip3 install --no-cache-dir -r /opt/fortinet-zoho-sync/requirements.txt

# Make run script executable
RUN chmod a+x /opt/fortinet-zoho-sync/run.sh

# Labels
LABEL \
    io.hass.name="Fortinet Zoho Calendar Sync" \
    io.hass.description="Sincronizzazione automatica scadenze firewall Fortinet con calendario Zoho" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    maintainer="Your Name <your.email@example.com>"

CMD ["/opt/fortinet-zoho-sync/run.sh"]
