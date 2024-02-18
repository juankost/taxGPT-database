# Alternative for the docker image: 
# https://github.com/joyzoursky/docker-python-chromedriver/blob/master/py-debian/3.9-selenium/Dockerfile
FROM selenium/standalone-chrome

# Run commands as root
USER root

# Install Python pip
RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python3 get-pip.py && \
    python3 -m pip install --no-cache-dir --upgrade pip selenium

# Copy the requirements file and install Python dependencies
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy the application code to the container
COPY ./app /app

# Expose port 8080
EXPOSE 8080

# Copy the startup script to the container
COPY ./startup.sh /app/startup.sh

# Make sure the startup script is executable
RUN chmod +x /app/startup.sh

# Define the command to run the application
CMD ["/bin/bash", "/app/startup.sh"]