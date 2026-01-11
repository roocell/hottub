FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY engine/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY geckolib ./geckolib
RUN pip install --no-cache-dir ./geckolib
COPY engine/spa_engine ./spa_engine
EXPOSE 8000
CMD ["python","-m","spa_engine"]
