#!/bin/bash
# Wrapper around conda-forge's dasgoclient (#96), installed as
# /usr/local/bin/dasgoclient; the real binary is in /usr/local/libexec.
#
# 1. dasgoclient reads BEARER_TOKEN_FILE, which in coffea-casa points at the
#    XCache token. cmsweb rejects that token (401), and once dasgoclient has
#    a token it ignores any X.509 proxy, so hide it. Without a proxy,
#    dasgoclient then asks the user to run voms-proxy-init. A CMS token can
#    still be given with -token or BEARER_TOKEN.
# 2. In token mode dasgoclient checks cmsweb.cern.ch's certificate against
#    Go's system roots, which lack the CERN Grid CA ("x509: certificate signed
#    by unknown authority"). Add the IGTF CA directory. SSL_CERT_DIR replaces
#    Go's default directories, so keep those as well.
real=/usr/local/libexec/dasgoclient

unset BEARER_TOKEN_FILE

# 3. dasgoclient caches DAS maps from GitHub in ~/.dasmaps for 24 hours and
#    saves an HTTP error body (e.g. "404: Not Found") as if it were the maps,
#    after which every query fails with "Wrong DAS key". Drop such a file so
#    the next run downloads the maps again.
maps="${HOME}/.dasmaps/das_maps_dbs_prod.js"
if [ -f "$maps" ] && ! grep -q '"das_map"' "$maps"; then
    rm -f "$maps"
fi

grid_ca="${X509_CERT_DIR:-/etc/grid-security/certificates}"
export SSL_CERT_DIR="${SSL_CERT_DIR:-/etc/pki/tls/certs:/etc/ssl/certs}:${grid_ca}"

exec "$real" "$@"
