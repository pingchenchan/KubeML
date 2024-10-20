# Use Node.js image to build and serve the React app
FROM node:14-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Copy all source files
COPY . .

# Expose the development server port
EXPOSE 3001

# Start the React development server
CMD ["npm", "start"]
