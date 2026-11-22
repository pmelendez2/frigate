#!/bin/bash

set -euxo pipefail

NGINX_VERSION="1.31.9"
VOD_MODULE_VERSION="v1.9.1"
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
# Apply the VOD compatibility fix inside the function body.
vod_parser="/tmp/nginx-vod-module/vod/avc_hevc_parser.c"
signature='avc_hevc_parser_rbsp_trailing_bits(bit_reader_state_t* reader) {'

test "$(grep -Fxc "$signature" "$vod_parser")" -eq 1

vod_tmp="$(mktemp)"
awk '
    /^avc_hevc_parser_rbsp_trailing_bits\(bit_reader_state_t\* reader\) \{$/ {
        print
        print "\t// Frigate VOD parser compatibility fix"
        print "\treturn TRUE;"
        next
    }
    { print }
' "$vod_parser" > "$vod_tmp"

cat "$vod_tmp" > "$vod_parser"
rm -f -- "$vod_tmp"

grep -F -A 3 "$signature" "$vod_parser"


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
    --with-cc-opt="-O3 -Wno-error=implicit-fallthrough"

make CC="ccache gcc" -j2
make install
test -x /usr/local/nginx/sbin/nginx
rm -rf /usr/local/nginx/html /usr/local/nginx/conf/*.default
