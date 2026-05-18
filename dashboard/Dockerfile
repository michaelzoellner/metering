FROM python:3.11-slim

WORKDIR /app

COPY ./dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app and pages folder
COPY ./dashboard/app.py .
COPY ./dashboard/assets ./assets

EXPOSE 8050

CMD ["python", "app.py"]