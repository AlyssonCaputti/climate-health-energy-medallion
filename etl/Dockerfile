FROM python:3.12-slim
WORKDIR /app

# Dependências antes do código: mudo um .py e o pip install vem do cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "run.py"]
