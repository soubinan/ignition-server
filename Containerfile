FROM python:slim

LABEL maintainer="https://github.com/soubinan"

WORKDIR /app

RUN apt-get update -y && apt-get upgrade -y && apt-get install wget curl -y && apt-get clean -y
RUN wget "https://github.com/coreos/butane/releases/latest/download/butane-x86_64-unknown-linux-gnu" -O /usr/bin/butane && \
    chmod +x /usr/bin/butane

COPY requirements.txt requirements.txt

RUN pip install -U pip && \
    pip install -r requirements.txt --no-cache-dir

COPY main.py main.py

ARG version=1.0.0
ENV API_VERSION=$version \
    READ_APPEND_ONLY=false

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -s --fail http://127.0.0.1:8000 || exit 1

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--use-colors"]
CMD ["--workers", "1"]