# A remote login (the user, 2026-11-10: "just prepare for using docker on platform as a way to login remotely with only
# the login-app"): the login app alone, its users in /data, behind the https front of compose.yaml, which shares this
# container's network so the app still answers only 127.0.0.1. Built from this checkout and liminal-libs' (compose.yaml
# gives it as the `libs` context), so it runs the code here, pushed or not.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIMINAL_LOGIN_DIR=/data/login \
    LIMINAL_LOGIN_CFG=/config/liminal-login.cfg \
    LIMINAL_LOGIN_PORT=8795

COPY --from=libs pyproject.toml README.md /src/liminal-libs/
COPY --from=libs src /src/liminal-libs/src
COPY pyproject.toml README.md /src/liminal-login/
COPY src /src/liminal-login/src
RUN pip install --no-cache-dir /src/liminal-libs /src/liminal-login

VOLUME /data
CMD ["liminal-login", "serve", "--no-browser", "--port", "8795"]
