FROM python:3.11-slim

WORKDIR /app

# Install Microsoft Edge and Edgedriver for Selenium support
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && curl -sS --retry 5 --retry-connrefused --retry-delay 2 https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg \
    && echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge.list \
    && apt-get update && apt-get install -y microsoft-edge-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-downloaded Edgedriver if it exists, otherwise download dynamically
COPY edgedriver_linux64.zip* /tmp/
RUN if [ -f /tmp/edgedriver_linux64.zip ]; then \
        unzip /tmp/edgedriver_linux64.zip -d /usr/bin/; \
        rm /tmp/edgedriver_linux64.zip; \
    else \
        EDGE_VERSION=$(microsoft-edge-stable --version | awk '{print $3}') \
        && curl -sS -L --retry 5 --retry-connrefused --retry-delay 2 -o /tmp/edgedriver_linux64.zip "https://msedgedriver.microsoft.com/${EDGE_VERSION}/edgedriver_linux64.zip" \
        && unzip /tmp/edgedriver_linux64.zip -d /usr/bin/ \
        && rm /tmp/edgedriver_linux64.zip; \
    fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
