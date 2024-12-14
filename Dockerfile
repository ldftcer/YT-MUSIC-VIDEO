FROM node:18-slim

# Установим зависимости для FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Установите зависимости вашего проекта (если нужно)
WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .

CMD ["npm", "start"]
