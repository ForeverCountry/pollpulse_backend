FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apk update && apk add --no-cache gcc musl-dev libffi-dev

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown appuser:appgroup /entrypoint.sh

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
