# Use Node.js image to build the React app
FROM node:14-alpine as build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Copy all source files and build the project
COPY . .
RUN npm run build

# Use Nginx to serve the static files
FROM nginx:stable-alpine
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
