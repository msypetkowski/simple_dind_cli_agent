FROM docker:dind

RUN apk add --no-cache \
        python3 \
        py3-pip \
        git \
        curl \
        wget \
        bash \
        build-base \
        ca-certificates \
    && ln -sf /usr/bin/python3 /usr/bin/python

RUN pip install --no-cache-dir --break-system-packages \
        openai \
        openai-agents \
        streamlit \
        duckduckgo-search

WORKDIR /app
COPY main.py .
