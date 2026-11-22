#!/bin/bash

set -euxo pipefail

NGINX_VERSION="1.31.9"
VOD_MODULE_VERSION="v1.9.1"
SECURE_TOKEN_MODULE_VERSION="1.5"
SET_MISC_MODULE_VERSION="v0.33"
NGX_DEVEL_KIT_VERSION="v0.3.3"

source /etc/os-release

if [[ "$VERSION_ID" == "12" ]]; then
    sed -i '/^Types:/s/deb/& deb-src/' /etc/apt/sources.list.d/debian.sources
else
    cp /etc/apt/sources.list /etc/apt/sources.list.d/sources-src.list
    sed -i 's|deb http|deb-src http|g' /etc/apt/sources.list.d/sources-src.list
fi

apt-get update
apt-get -yqq build-dep nginx

apt-get -yqq install --no-install-recommends ca-certificates wget
update-ca-certificates -f
apt install -y ccache

export PATH="/usr/lib/ccache:$PATH"

mkdir /tmp/nginx
wget -nv https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz
tar -zxf nginx-${NGINX_VERSION}.tar.gz -C /tmp/nginx --strip-components=1
rm nginx-${NGINX_VERSION}.tar.gz
mkdir /tmp/nginx-vod-module
wget -nv https://github.com/dio-az/nginx-vod-module/archive/refs/tags/${VOD_MODULE_VERSION}.tar.gz
tar -zxf ${VOD_MODULE_VERSION}.tar.gz -C /tmp/nginx-vod-module --strip-components=1
rm ${VOD_MODULE_VERSION}.tar.gz
    # Patch MAX_CLIPS to allow more clips to be added than the default 128
sed -i 's/MAX_CLIPS (128)/MAX_CLIPS (1080)/g' /tmp/nginx-vod-module/vod/media_set.h
patch -d /tmp/nginx-vod-module/ -p1 << 'EOF'
--- a/vod/avc_hevc_parser.c
+++ b/vod/avc_hevc_parser.c
@@ -2,5 +2,8 @@

 bool_t
 avc_hevc_parser_rbsp_trailing_bits(bit_reader_state_t* reader) {
+	// https://github.com/blakeblackshear/frigate/issues/4572
+	return TRUE;
+
 	uint32_t one_bit;

EOF


mkdir /tmp/nginx-secure-token-module
# Use a pinned source mirror while the Kaltura repository is unavailable.
SECURE_TOKEN_MODULE_REF="3c34bd46947b337703c9e009c3ca212b6162a070"
wget -nv -O secure-token-module.tar.gz https://github.com/nginx-modules/nginx-secure-token-module/archive/${SECURE_TOKEN_MODULE_REF}.tar.gz
tar -zxf secure-token-module.tar.gz -C /tmp/nginx-secure-token-module --strip-components=1
rm secure-token-module.tar.gz

# Adapt the pinned secure-token module to nginx 1.23+ headers API.
# nginx now stores Cache-Control as ngx_table_elt_t *, not ngx_array_t.
# Fail the build if the pinned module source no longer matches.
secure_token_source=/tmp/nginx-secure-token-module/ngx_http_secure_token_filter_module.c
awk '
    /ngx_http_secure_token_set_expires\(/ && !replacements { in_function = 1 }
    in_function && /ngx_uint_t[[:space:]]+i;/ {
        removed_i++
        next
    }
    in_function && /ngx_table_elt_t[[:space:]]+\*expires,[[:space:]]*\*cc,[[:space:]]*\*\*ccp;/ {
        sub(/,[[:space:]]*\*\*ccp;/, ";")
        declarations++
        print
        next
    }
    in_function && /ccp = r->headers_out.cache_control.elts;/ {
        replacements++
        skipping = 1
        print "    cc = r->headers_out.cache_control;"
        print "    if (cc == NULL) {"
        print "        cc = ngx_list_push(&r->headers_out.headers);"
        print "        if (cc == NULL) {"
        print "            return NGX_ERROR;"
        print "        }"
        print "        r->headers_out.cache_control = cc;"
        print "    }"
        print "    cc->hash = 1;"
        print "    ngx_str_set(&cc->key, \"Cache-Control\");"
        next
    }
    skipping {
        if (/^[[:space:]]*if \(expires_time == 0\) \{/) {
            skipping = 0
            in_function = 0
            print
        }
        next
    }
    { print }
    END {
        if (replacements != 1 || removed_i != 1 ||
            declarations != 1 || skipping) {
            print "ERROR: secure-token header API patch did not match" > "/dev/stderr"
            exit 1
        }
    }
' "$secure_token_source" > "${secure_token_source}.new"
mv "${secure_token_source}.new" "$secure_token_source"
grep -q 'cc = r->headers_out.cache_control;' "$secure_token_source"


mkdir /tmp/ngx_devel_kit
wget https://github.com/vision5/ngx_devel_kit/archive/refs/tags/${NGX_DEVEL_KIT_VERSION}.tar.gz
tar -zxf ${NGX_DEVEL_KIT_VERSION}.tar.gz -C /tmp/ngx_devel_kit --strip-components=1
rm ${NGX_DEVEL_KIT_VERSION}.tar.gz

mkdir /tmp/nginx-set-misc-module
wget https://github.com/openresty/set-misc-nginx-module/archive/refs/tags/${SET_MISC_MODULE_VERSION}.tar.gz
tar -zxf ${SET_MISC_MODULE_VERSION}.tar.gz -C /tmp/nginx-set-misc-module --strip-components=1
rm ${SET_MISC_MODULE_VERSION}.tar.gz

cd /tmp/nginx

./configure --prefix=/usr/local/nginx \
    --with-file-aio \
    --with-http_sub_module \
    --with-http_ssl_module \
    --with-http_v2_module \
    --with-http_auth_request_module \
    --with-http_realip_module \
    --with-threads \
    --add-module=../ngx_devel_kit \
    --add-module=../nginx-set-misc-module \
    --add-module=../nginx-vod-module \
    --add-module=../nginx-secure-token-module \
    --with-cc-opt="-O3 -Wno-error=implicit-fallthrough"

make CC="ccache gcc" -j2
make install
test -x /usr/local/nginx/sbin/nginx
rm -rf /usr/local/nginx/html /usr/local/nginx/conf/*.default
