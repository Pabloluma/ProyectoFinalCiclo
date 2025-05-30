FROM python:3.9-slim

# Instala dependencias necesarias para compilar mysqlclient
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia los archivos
COPY . /app

# Instala las dependencias de Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expón el puerto 8000
EXPOSE 8000

# Comando para producción con Gunicorn
CMD ["gunicorn", "ProyectoFinalCiclo.wsgi:application", "--bind", "0.0.0.0:8000"]