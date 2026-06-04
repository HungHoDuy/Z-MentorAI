FROM python:3.11-slim

WORKDIR /app

# Install Microsoft Edge and Edgedriver for Selenium support
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && curl -sS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg \
    && echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge.list \
    && apt-get update && apt-get install -y microsoft-edge-stable \
    && EDGE_VERSION=$(microsoft-edge-stable --version | awk '{print $3}') \
    && wget -q "https://msedgedriver.azureedge.net/${EDGE_VERSION}/edgedriver_linux64.zip" \
    && unzip edgedriver_linux64.zip -d /usr/bin/ \
    && rm edgedriver_linux64.zip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
