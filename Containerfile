FROM python:slim

LABEL maintainer="https://github.com/soubinan"

WORKDIR /app
VOLUME [ "/app/templates" ]

RUN apt-get update -y && apt-get upgrade -y && apt-get install wget -y && apt-get clean -y
RUN wget "https://github.com/coreos/butane/releases/latest/download/butane-x86_64-unknown-linux-gnu" -O ./butane && \
    chmod +x ./butane

COPY main.py main.py
COPY requirements.txt requirements.txt

RUN pip install -U pip && \
    pip install -r requirements.txt

EXPOSE 8000
CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
