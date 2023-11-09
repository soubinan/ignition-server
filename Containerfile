FROM python:slim

LABEL maintainer="https://github.com/soubinan"

WORKDIR /app

RUN apt-get update && apt-get install wget -y && apt-get autoclean
RUN wget https://github.com/coreos/butane/releases/latest/download/butane-x86_64-unknown-linux-gnu -O ./butane && \
    chmod +x ./butane
RUN pip install python-dotenv

COPY coreos/server.py ./server.py

VOLUME [ "/app/templates" ]

EXPOSE 8899

CMD ["python", "server.py"]
