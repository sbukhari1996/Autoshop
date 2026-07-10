FROM nginx:alpine

# Install envsubst (part of gettext)
RUN apk add --no-cache gettext

COPY src/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Railway sets $PORT dynamically; nginx listens on it.
# API_URL must be set to the FastAPI service public URL, e.g.:
#   https://autoshop-production-b0a7up.railway.app
ENV PORT=80
ENV API_URL=http://localhost:8000

# envsubst replaces $PORT and $API_URL in the nginx template at container start
CMD ["/bin/sh", "-c", "envsubst '${PORT} ${API_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
