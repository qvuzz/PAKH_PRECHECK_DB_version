# Dockerfile cho PAKH Precheck - VNPT VinaPhone
FROM python:3.11-slim

# Thiết lập biến môi trường chuẩn
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=1234 \
    TZ=Asia/Ho_Chi_Minh

# Cài đặt múi giờ Việt Nam và các gói công cụ hệ thống tối thiểu
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    ca-certificates \
    libgomp1 \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sao chép và cài đặt các thư viện Python (kèm llama-cpp-python CPU wheel để chạy Qwen)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu && \
    playwright install-deps chromium && \
    playwright install chromium

# Sao chép toàn bộ mã nguồn ứng dụng
COPY . .

# Tạo các thư mục phục vụ lưu trữ file và kết quả
RUN mkdir -p /app/result /app/scratch /app/output /app/sapccheck /app/data /app/models

# Mở cổng 1234 cho Web Dashboard
EXPOSE 1234

# Kiểm tra trạng thái hoạt động của Container
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:1234/api/status || exit 1

# Khởi chạy hệ thống Web Dashboard
CMD ["python", "dashboard.py"]
