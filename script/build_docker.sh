docker-compose down
docker-compose build --no-cache backend
docker-compose up -d
docker-compose logs backend