FROM nginx:alpine
COPY src/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
CMD ["/bin/sh", "-c", "echo \">>> Railway PORT env var is: ${PORT:-NOT_SET} <<<\" && sed -i \"s/NGINX_PORT/${PORT:-80}/\" /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
