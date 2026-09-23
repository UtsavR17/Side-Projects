FROM python:3.12-slim

WORKDIR /srv

# System deps occasionally needed by scikit-learn/numpy wheels on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ml.txt ./
# ML extras are optional — don't fail the image if shap/lightgbm can't build.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-ml.txt || true

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
