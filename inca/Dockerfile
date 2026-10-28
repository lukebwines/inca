FROM python:3.13-alpine
WORKDIR /opt/inca
COPY app.py auth.py splits.py index.html login.html excel_export.py export_schema.json ./
COPY vendor ./vendor
ENV INCA_INGRESS=1 INCA_DATA=/data INCA_PORT=8099 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8099 8100
CMD ["python", "app.py"]
